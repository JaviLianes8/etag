"""Parse ETag, If-Match and If-None-Match field values (RFC 9110 sections 8.8.3, 13.1)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeAlias

from ._plain import check_flag, octets, text, type_name
from ._tag import EntityTag, format_etag, is_etagc

WILDCARD = "*"
_OWS = " \t"

Header: TypeAlias = str | bytes | bytearray | Sequence[str | bytes | bytearray]


def field_value(header: Header) -> str:
    """Return one field value from text, Latin-1 bytes, or a list of field lines."""
    if isinstance(header, str):
        return text(header)
    if isinstance(header, (bytes, bytearray)):
        return octets(header)
    if isinstance(header, Sequence):
        # Section 5.3: field lines with the same name join with a comma. Blank lines
        # carry no element, so they are dropped rather than turned into one.
        lines = (_line(line) for line in header)
        return ", ".join(line for line in lines if line.strip(_OWS))
    raise TypeError(f"header must be str, bytes or a list of them, not {type_name(header)}")


def _line(line: object) -> str:
    if isinstance(line, str):
        return text(line)
    if isinstance(line, (bytes, bytearray)):
        return octets(line)
    raise TypeError(f"field line must be str or bytes, not {type_name(line)}")


def is_wildcard(header: Header) -> bool:
    """Report whether a field value is the ``*`` wildcard (and not the tag ``"*"``).

    Malformed values are not the wildcard; only a wrong argument type raises.

    >>> is_wildcard(" * "), is_wildcard('"*"'), is_wildcard('*, "a"')
    (True, False, False)
    """
    return field_value(header).strip(_OWS) == WILDCARD


def _element(field: str, i: int) -> tuple[EntityTag, int]:
    """Read one entity-tag starting at ``i``; return it and the index after it."""
    weak = field.startswith("W/", i)
    if weak:
        i += 2
    if i >= len(field) or field[i] != '"':
        raise ValueError(f"expected an opaque-tag at position {i}")
    start = i + 1
    end = field.find('"', start)
    if end == -1:
        raise ValueError(f"unterminated opaque-tag at position {i}")
    for j in range(start, end):
        if not is_etagc(field[j]):
            raise ValueError(f"invalid character in opaque-tag at position {j}")
    return EntityTag(field[start:end], weak), end + 1


def _skip_ows(field: str, i: int) -> int:
    while i < len(field) and field[i] in _OWS:
        i += 1
    return i


def parse(header: Header) -> list[EntityTag]:
    """Parse a field value into its entity-tags, in order.

    Each item is an :class:`EntityTag`, which unpacks as ``(value, weak)``. Empty list
    elements are skipped (section 5.6.1.2) and a list of field lines is joined first.
    A bare ``*`` wildcard yields ``[EntityTag("*")]``; use :func:`is_wildcard` to tell
    it from the tag ``"*"``. Raises ``ValueError`` on malformed input or when no tag is
    present; its message gives the position in the (joined) field value.

    >>> parse('"a", , W/"b"')
    [EntityTag(value='a', weak=False), EntityTag(value='b', weak=True)]
    >>> parse([b'"a"', 'W/"b"']) == [("a", False), ("b", True)]
    True
    """
    field = field_value(header)
    if field.strip(_OWS) == WILDCARD:
        return [EntityTag(WILDCARD)]
    entries: list[EntityTag] = []
    i = 0
    while True:
        i = _skip_ows(field, i)
        if i >= len(field):
            break
        if field[i] == ",":
            i += 1
            continue
        tag, i = _element(field, i)
        entries.append(tag)
        i = _skip_ows(field, i)
        if i < len(field) and field[i] != ",":
            raise ValueError(f"expected a comma at position {i}")
    if not entries:
        raise ValueError("no entity-tag found")
    return entries


def parse_one(etag: str | EntityTag) -> EntityTag:
    """Read exactly one entity-tag, rejecting lists, empty elements and the wildcard."""
    if isinstance(etag, EntityTag):
        value, weak = tuple.__getitem__(etag, 0), tuple.__getitem__(etag, 1)
        check_flag("weak", weak)
        format_etag(value, weak=weak)  # validates the opaque value
        return EntityTag(text(value), weak)
    if not isinstance(etag, str):
        raise TypeError(f"entity-tag must be a str or EntityTag, not {type_name(etag)}")
    field = text(etag).strip(_OWS)
    tag, end = _element(field, 0)
    if end != len(field):
        raise ValueError("expected a single entity-tag")
    return tag
