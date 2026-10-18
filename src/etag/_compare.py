"""Compare entity-tags with the strong and weak functions of RFC 9110 section 8.8.3.2."""

from __future__ import annotations

from ._parse import Header, field_value, parse_one, tags, wildcard
from ._plain import check_flag
from ._tag import EntityTag


def strong_compare(a: str | EntityTag, b: str | EntityTag) -> bool:
    """Report whether two entity-tags are both strong and have the same opaque value.

    Each argument is one entity-tag, as text or an :class:`EntityTag`; anything else
    raises ``ValueError`` (malformed text) or ``TypeError`` (another type).

    >>> strong_compare('"1"', '"1"'), strong_compare('W/"1"', '"1"')
    (True, False)
    """
    left, right = parse_one(a), parse_one(b)
    return not left.weak and not right.weak and left.value == right.value


def weak_compare(a: str | EntityTag, b: str | EntityTag) -> bool:
    """Report whether two entity-tags have the same opaque value, weak or not.

    Arguments and errors are as for :func:`strong_compare`.

    >>> weak_compare('W/"1"', '"1"'), weak_compare('W/"1"', 'W/"2"')
    (True, False)
    """
    return parse_one(a).value == parse_one(b).value


def matches(header: Header, etag: str | EntityTag, *, weak: bool = True) -> bool:
    """Report whether ``etag`` matches a member of an If-None-Match or If-Match value.

    ``header`` is the field value (text, bytes, or a list of field lines) and ``etag``
    is a single entity-tag. With ``weak=True`` (the default, the If-None-Match rule)
    the weak comparison is used; with ``weak=False`` (the If-Match rule) the strong one.
    A ``*`` wildcard matches any tag. Malformed input raises ``ValueError`` and a
    ``weak`` that is not a bool raises ``TypeError``; to apply the RFC outcome for
    malformed requests instead, use :func:`if_match` or :func:`if_none_match`.

    >>> matches('W/"a", "b"', '"a"'), matches('W/"a", "b"', '"a"', weak=False)
    (True, False)
    """
    check_flag("weak", weak)
    target = parse_one(etag)
    field = field_value(header)
    if wildcard(field):
        return True
    listed = tags(field)
    if not weak and target.weak:
        return False
    return any(tag.value == target.value and (weak or not tag.weak) for tag in listed)
