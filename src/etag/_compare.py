"""Compare entity-tags with the strong and weak functions of RFC 9110 section 8.8.3.2."""

from __future__ import annotations

from ._parse import Header, is_wildcard, parse, parse_one
from ._tag import EntityTag


def strong_compare(a: str | EntityTag, b: str | EntityTag) -> bool:
    """Report whether two entity-tags are both strong and have the same opaque value."""
    left, right = parse_one(a), parse_one(b)
    return not left.weak and not right.weak and left.value == right.value


def weak_compare(a: str | EntityTag, b: str | EntityTag) -> bool:
    """Report whether two entity-tags have the same opaque value, weak or not."""
    return parse_one(a).value == parse_one(b).value


def matches(header: Header, etag: str | EntityTag, *, weak: bool = True) -> bool:
    """Report whether ``etag`` matches a member of an If-None-Match or If-Match value.

    ``header`` is the field value (text, bytes, or a list of field lines) and ``etag``
    is a single entity-tag. With ``weak=True`` (the default, the If-None-Match rule)
    the weak comparison is used; with ``weak=False`` (the If-Match rule) the strong one.
    A ``*`` wildcard matches any tag. Malformed input raises ``ValueError``; to apply
    the RFC outcome for malformed requests instead, use :func:`if_match` or
    :func:`if_none_match`.
    """
    target = parse_one(etag)
    if is_wildcard(header):
        return True
    compare = weak_compare if weak else strong_compare
    return any(compare(tag, target) for tag in parse(header))
