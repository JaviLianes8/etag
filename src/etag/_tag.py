"""The entity-tag value type and the ways to build one (RFC 9110 section 8.8.3)."""

from __future__ import annotations

import hashlib
from typing import NamedTuple


def is_etagc(char: str) -> bool:
    """Report whether a character may appear inside an opaque-tag (etagc)."""
    code = ord(char)
    return code == 0x21 or 0x23 <= code <= 0x7E or 0x80 <= code <= 0xFF


def format_etag(value: str, *, weak: bool = False) -> str:
    """Quote an opaque value chosen by the server, such as a revision number.

    ``format_etag("123-a")`` returns ``'"123-a"'`` and ``weak=True`` adds the ``W/``
    prefix. Raises ``ValueError`` if ``value`` holds a character the grammar forbids
    (a double quote, a space, a control character or anything above U+00FF), and
    ``TypeError`` if it is not a string.
    """
    if not isinstance(value, str):
        raise TypeError(f"opaque value must be a str, not {type(value).__name__}")
    for index, char in enumerate(value):
        if not is_etagc(char):
            raise ValueError(f"invalid character {char!r} in opaque-tag at position {index}")
    quoted = f'"{value}"'
    return f"W/{quoted}" if weak else quoted


class EntityTag(NamedTuple):
    """One entity-tag: the opaque value without its quotes, and whether it is weak.

    It unpacks and compares like the ``(value, weak)`` tuple it is. ``str()`` gives the
    header form, validated as :func:`format_etag` does.
    """

    value: str
    weak: bool = False

    def __str__(self) -> str:
        return format_etag(self.value, weak=self.weak)


def make_etag(data: bytes | bytearray | memoryview | str, *, weak: bool = False) -> str:
    """Return a quoted entity-tag derived from ``data``.

    ``data`` is hashed with SHA-256; text is encoded as UTF-8 first. The result is a
    double-quoted opaque-tag, prefixed with ``W/`` when ``weak`` is set.
    """
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return format_etag(hashlib.sha256(raw).hexdigest(), weak=weak)
