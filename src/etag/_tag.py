"""The entity-tag value type and the ways to build one (RFC 9110 section 8.8.3)."""

from __future__ import annotations

import hashlib
from typing import NamedTuple, cast

from ._plain import as_octets, as_text, check_flag, type_name


def is_etagc(char: str) -> bool:
    """Report whether a character may appear inside an opaque-tag (etagc)."""
    code = ord(char)
    return code == 0x21 or 0x23 <= code <= 0x7E or 0x80 <= code <= 0xFF


def format_etag(value: str, *, weak: bool = False) -> str:
    """Quote an opaque value chosen by the server, such as a revision number.

    Raises ``ValueError`` if ``value`` holds a character the grammar forbids (a double
    quote, a space, a control character or anything above U+00FF), and ``TypeError``
    if ``value`` is not a string or ``weak`` is not a bool.

    >>> format_etag("123-a")
    '"123-a"'
    >>> format_etag("123-a", weak=True)
    'W/"123-a"'
    """
    plain = as_text(value)
    if plain is None:
        raise TypeError(f"opaque value must be a str, not {type_name(value)}")
    check_flag("weak", weak)
    for index, char in enumerate(plain):
        if not is_etagc(char):
            raise ValueError(f"U+{ord(char):04X} is not allowed in an opaque-tag at {index}")
    quoted = f'"{plain}"'
    return f"W/{quoted}" if weak else quoted


class EntityTag(NamedTuple):
    """One entity-tag: the opaque value without its quotes, and whether it is weak.

    It unpacks and compares like the ``(value, weak)`` tuple it is. ``str()`` gives the
    header form, validated as :func:`format_etag` does.

    >>> tag = EntityTag("123-a", weak=True)
    >>> str(tag)
    'W/"123-a"'
    >>> value, weak = tag
    >>> (value, weak)
    ('123-a', True)
    """

    value: str
    weak: bool = False

    def __str__(self) -> str:
        return format_etag(self.value, weak=self.weak)


def make_etag(data: bytes | bytearray | memoryview | str, *, weak: bool = False) -> str:
    """Return a quoted entity-tag derived from ``data``.

    ``data`` is hashed with SHA-256; text is encoded as UTF-8 first. At run time any
    other object that exposes contiguous bytes (an ``array.array``, say) is hashed as
    those bytes too, although the annotation names only the common types. The result
    is a double-quoted opaque-tag of 64 lower-case hexadecimal digits, prefixed with
    ``W/`` when ``weak`` is set. Raises ``TypeError`` for anything else or for a
    ``weak`` that is not a bool, and ``ValueError`` naming the code point and its index
    for text holding a lone surrogate.

    >>> make_etag(b"abc")[:11]
    '"ba7816bf8f'
    >>> make_etag("abc", weak=True) == "W/" + make_etag(b"abc")
    True
    """
    check_flag("weak", weak)
    plain = as_text(data)
    if plain is not None:
        try:
            encoded = plain.encode("utf-8")
        except UnicodeEncodeError as error:
            # Re-raised without the encoder's error, which would carry the whole text.
            code, at = ord(plain[error.start]), error.start
            bad = f"U+{code:04X} cannot be encoded as UTF-8 at {at}"
        else:
            return format_etag(hashlib.sha256(encoded).hexdigest(), weak=weak)
        raise ValueError(bad)
    octets = as_octets(data)
    try:
        # Any other object exporting a buffer is read through it, as documented above.
        raw = memoryview(cast(memoryview, data) if octets is None else octets)
    except TypeError:
        raise TypeError(f"data must be bytes-like or str, not {type_name(data)}") from None
    return format_etag(hashlib.sha256(raw).hexdigest(), weak=weak)
