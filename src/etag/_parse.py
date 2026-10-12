"""Parse ETag, If-Match and If-None-Match field values (RFC 9110 sections 8.8.3, 13.1)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeAlias

from ._tag import EntityTag, is_etagc

WILDCARD = "*"
_OWS = " \t"

Header: TypeAlias = str | bytes | bytearray | Sequence[str | bytes | bytearray]


def field_value(header: Header) -> str:
    """Return one field value from text, Latin-1 bytes, or a list of field lines."""
    if isinstance(header, str):
        return header
    if isinstance(header, (bytes, bytearray)):
        return bytes(header).decode("latin-1")
    if isinstance(header, Sequence):
        # Section 5.3: field lines with the same name join with a comma. Blank lines
        # carry no element, so they are dropped rather than turned into one.
        lines = (_line(line) for line in header)
        return ", ".join(line for line in lines if line.strip(_OWS))
    raise TypeError(f"header must be str, bytes or a list of them, not {type(header).__name__}")


def _line(line: object) -> str:
    if isinstance(line, str):
        return line
    if isinstance(line, (bytes, bytearray)):
        return bytes(line).decode("latin-1")
    raise TypeError(f"field line must be str or bytes, not {type(line).__name__}")


def is_wildcard(header: Header) -> bool:
    """Report whether a field value is the ``*`` wildcard (and not the tag ``"*"``)."""
    return field_value(header).strip(_OWS) == WILDCARD


def _element(text: str, i: int) -> tuple[EntityTag, int]:
    """Read one entity-tag starting at ``i``; return it and the index after it."""
    weak = text.startswith("W/", i)
    if weak:
        i += 2
    if i >= len(text) or text[i] != '"':
        raise ValueError(f"expected an opaque-tag at position {i}")
    start = i + 1
    end = text.find('"', start)
    if end == -1:
        raise ValueError("unterminated opaque-tag")
    for j in range(start, end):
        if not is_etagc(text[j]):
            raise ValueError(f"invalid character in opaque-tag at position {j}")
    return EntityTag(text[start:end], weak), end + 1


def _skip_ows(text: str, i: int) -> int:
    while i < len(text) and text[i] in _OWS:
        i += 1
    return i


def parse(header: Header) -> list[EntityTag]:
    """Parse a field value into its entity-tags, in order.

    Each item is an :class:`EntityTag`, which unpacks as ``(value, weak)``. Empty list
    elements are skipped (section 5.6.1.2) and a list of field lines is joined first.
    A bare ``*`` wildcard yields ``[EntityTag("*")]``; use :func:`is_wildcard` to tell
    it from the tag ``"*"``. Raises ``ValueError`` on malformed input or when no tag is
    present.
    """
    text = field_value(header).strip(_OWS)
    if text == WILDCARD:
        return [EntityTag(WILDCARD)]
    entries: list[EntityTag] = []
    i = 0
    while True:
        i = _skip_ows(text, i)
        if i >= len(text):
            break
        if text[i] == ",":
            i += 1
            continue
        tag, i = _element(text, i)
        entries.append(tag)
        i = _skip_ows(text, i)
        if i < len(text) and text[i] != ",":
            raise ValueError(f"expected a comma at position {i}")
    if not entries:
        raise ValueError("no entity-tag found")
    return entries


def parse_one(etag: str | EntityTag) -> EntityTag:
    """Read exactly one entity-tag, rejecting lists, empty elements and the wildcard."""
    if isinstance(etag, EntityTag):
        str(etag)  # validates the opaque value
        return etag
    if not isinstance(etag, str):
        raise TypeError(f"entity-tag must be a str or EntityTag, not {type(etag).__name__}")
    text = etag.strip(_OWS)
    tag, end = _element(text, 0)
    if end != len(text):
        raise ValueError("expected a single entity-tag")
    return tag
