"""Parse ETag, If-Match and If-None-Match field values (RFC 9110 sections 8.8.3, 13.1)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeAlias, cast

from ._plain import as_octets, as_text, check_flag, type_name
from ._tag import EntityTag, format_etag, is_etagc

WILDCARD = "*"
_OWS = " \t"

Header: TypeAlias = str | bytes | bytearray | Sequence[str | bytes | bytearray]
"""A header argument: text, bytes read as Latin-1, or a list of field lines to join."""


def read_field(header: Header) -> str | None:
    """The field value of text, Latin-1 bytes or field lines; ``None`` for no field line.

    The header is read once: a list of field lines by iterating it.
    """
    plain = as_text(header)
    if plain is not None:
        return plain
    octets = as_octets(header)
    if octets is not None:
        return octets.decode("latin-1")
    if issubclass(type(header), Sequence) and not issubclass(type(header), EntityTag):
        lines = [_line(line) for line in header]
        if not lines:
            return None
        # Section 5.3: field lines with the same name join with a comma. Blank lines
        # carry no element, so they are dropped rather than turned into one.
        return ", ".join(line for line in lines if line.strip(_OWS))
    raise TypeError(f"header must be str, bytes or a list of them, not {type_name(header)}")


def field_value(header: Header) -> str:
    """The field value; an empty list of field lines gives an empty value."""
    field = read_field(header)
    return "" if field is None else field


def _line(line: object) -> str:
    plain = as_text(line)
    if plain is not None:
        return plain
    octets = as_octets(line)
    if octets is not None:
        return octets.decode("latin-1")
    raise TypeError(f"field line must be str or bytes, not {type_name(line)}")


def wildcard(field: str) -> bool:
    """Report whether an exact field value is the ``*`` wildcard."""
    return field.strip(_OWS) == WILDCARD


def is_wildcard(header: Header) -> bool:
    """Report whether a field value is the ``*`` wildcard (and not the tag ``"*"``).

    Malformed values are not the wildcard; only a wrong argument type raises.

    >>> is_wildcard(" * "), is_wildcard('"*"'), is_wildcard('*, "a"')
    (True, False, False)
    """
    return wildcard(field_value(header))


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


def tags(field: str) -> list[EntityTag]:
    """Parse an exact field value; see :func:`parse`."""
    if wildcard(field):
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


def parse(header: Header) -> list[EntityTag]:
    """Parse a field value into its entity-tags, in order.

    Each item is an :class:`EntityTag`, which unpacks as ``(value, weak)``. Empty list
    elements are skipped (section 5.6.1.2) and a list of field lines is joined first.
    A bare ``*`` wildcard yields ``[EntityTag("*")]``; use :func:`is_wildcard` to tell
    it from the tag ``"*"``. Raises ``ValueError`` when no tag is present or the input
    is malformed, then with the position in the (joined) field value.

    >>> parse('"a", , W/"b"')
    [EntityTag(value='a', weak=False), EntityTag(value='b', weak=True)]
    >>> parse([b'"a"', 'W/"b"']) == [("a", False), ("b", True)]
    True
    """
    return tags(field_value(header))


def parse_one(etag: str | EntityTag) -> EntityTag:
    """Read exactly one entity-tag, rejecting lists, empty elements and the wildcard."""
    if issubclass(type(etag), EntityTag):
        # The tuple slots themselves: a subclass cannot replace the fields it reports.
        size = tuple.__len__(cast(EntityTag, etag))
        if size != 2:
            raise TypeError(f"an EntityTag has two fields, not {size}")
        value, weak = tuple.__getitem__(cast(EntityTag, etag), slice(None))
        plain = as_text(value)
        if plain is None:
            raise TypeError(f"opaque value must be a str, not {type_name(value)}")
        flag = check_flag("weak", weak)
        format_etag(plain, weak=flag)  # validates the opaque value
        return EntityTag(plain, flag)
    field = as_text(etag)
    if field is None:
        raise TypeError(f"entity-tag must be a str or EntityTag, not {type_name(etag)}")
    tag, end = _element(field, _skip_ows(field, 0))
    if _skip_ows(field, end) != len(field):
        raise ValueError(f"expected a single entity-tag, more at position {end}")
    return tag
