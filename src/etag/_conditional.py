"""Evaluate conditional requests on entity-tags (RFC 9110 sections 13.1 and 13.2)."""

from __future__ import annotations

from typing import Literal

from ._parse import Header, field_value, parse_one, read_field, tags, wildcard
from ._plain import as_text, check_flag, type_name
from ._tag import EntityTag

_SAFE_FOR_304 = ("GET", "HEAD")
# Section 13.2.1: these methods do not select a representation, so they ignore the fields.
_IGNORE_PRECONDITIONS = ("CONNECT", "OPTIONS", "TRACE")


def _state(etag: str | EntityTag | None, exists: bool | None) -> tuple[EntityTag | None, bool]:
    """Validate the current tag and decide whether a current representation exists."""
    current = None if etag is None else parse_one(etag)
    if exists is None:
        return current, current is not None
    present = check_flag("exists", exists)
    if not present and current is not None:
        raise ValueError("exists=False contradicts a current entity-tag")
    return current, present


def if_match(header: Header, etag: str | EntityTag | None, *, exists: bool | None = None) -> bool:
    """Evaluate an If-Match field value against the current entity-tag (13.1.1).

    ``etag`` is the selected representation's entity-tag, or ``None`` when there is
    none. ``exists`` says whether a current representation exists; it defaults to
    ``etag is not None`` and only needs passing for a resource served without a tag.
    ``*`` is true when one exists; a list is true when a member matches with the strong
    comparison; anything else, including a malformed value, is false. A false result
    means "respond 412". A malformed ``etag`` raises ``ValueError``, as does
    ``exists=False`` together with a tag; wrong argument types raise ``TypeError``.

    >>> if_match('"a", "b"', '"b"'), if_match('W/"b"', '"b"'), if_match("*", None)
    (True, False, False)
    """
    current, present = _state(etag, exists)
    field = field_value(header)
    if wildcard(field):
        return present
    try:
        listed = tags(field)
    except ValueError:
        return False
    if current is None or current.weak:
        return False
    return any(not tag.weak and tag.value == current.value for tag in listed)


def if_none_match(
    header: Header, etag: str | EntityTag | None, *, exists: bool | None = None
) -> bool:
    """Evaluate an If-None-Match field value against the current entity-tag (13.1.2).

    ``etag`` and ``exists`` work as in :func:`if_match`. ``*`` is false when a current
    representation exists; a list is false when a member matches with the weak
    comparison; anything else, including a malformed value, is true. A false result
    means 304 for GET and HEAD, 412 otherwise. Errors are as for :func:`if_match`.

    >>> if_none_match('W/"b"', '"b"'), if_none_match('"a"', '"b"'), if_none_match("*", None)
    (False, True, True)
    """
    current, present = _state(etag, exists)
    field = field_value(header)
    if wildcard(field):
        return not present
    try:
        listed = tags(field)
    except ValueError:
        return True
    if current is None:
        return True
    return not any(tag.value == current.value for tag in listed)


def if_range(header: Header, etag: str | EntityTag | None) -> bool:
    """Evaluate an entity-tag If-Range field value (13.1.5).

    True only when the value is a single entity-tag that matches ``etag`` with the
    strong comparison, so a weak tag never matches. An HTTP-date, a list or a malformed
    value is false here: evaluate the date form yourself before calling this. A false
    result means "ignore Range and send the whole representation". A malformed ``etag``
    raises ``ValueError`` and wrong argument types raise ``TypeError``.

    >>> if_range('"b"', '"b"'), if_range('W/"b"', 'W/"b"'), if_range("Fri, 26 Mar 2010", '"b"')
    (True, False, False)
    """
    current, _ = _state(etag, None)
    try:
        candidate = parse_one(field_value(header))
    except ValueError:
        return False
    if current is None or current.weak or candidate.weak:
        return False
    return candidate.value == current.value


def _field(header: Header | None) -> str | None:
    """The field value, or ``None`` for a field the request did not carry."""
    # A framework's getlist() returns [] for a field the request did not carry.
    return None if header is None else read_field(header)


# The keyword arguments below shadow the evaluators, so keep a reference to each.
_if_match = if_match
_if_none_match = if_none_match


def evaluate_preconditions(
    method: str,
    etag: str | EntityTag | None,
    *,
    if_match: Header | None = None,
    if_none_match: Header | None = None,
    exists: bool | None = None,
) -> Literal[304, 412] | None:
    """Return the status a precondition failure demands, or ``None`` to proceed.

    Follows the order of section 13.2.2 for the entity-tag fields of an origin server:
    If-Match first (412 when false), then If-None-Match (304 for ``GET`` and ``HEAD``,
    412 for other methods; method names are case-sensitive). ``CONNECT``, ``OPTIONS``
    and ``TRACE`` ignore both fields, and a redirect or an error your usual checks find
    first takes precedence (13.2.1). Pass ``None`` or an empty list for a field the
    request did not carry; ``exists`` works as in :func:`if_match`. If you also support
    dates, check If-Unmodified-Since only when If-Match is absent, If-Modified-Since
    only for ``GET`` and ``HEAD`` when If-None-Match is absent, and If-Range only for a
    ``GET`` with a Range (13.2.2). Errors are as for :func:`if_match`, and a ``method``
    that is not a str raises ``TypeError``.

    >>> current = '"v2"'
    >>> evaluate_preconditions("GET", current, if_none_match='"v2"')
    304
    >>> evaluate_preconditions("PUT", current, if_match='"v1"')
    412
    >>> evaluate_preconditions("PUT", None, if_none_match="*") is None
    True
    """
    verb = as_text(method)
    if verb is None:
        raise TypeError(f"method must be a str, not {type_name(method)}")
    current, present = _state(etag, exists)
    match, none_match = _field(if_match), _field(if_none_match)
    if verb in _IGNORE_PRECONDITIONS:
        return None
    if match is not None and not _if_match(match, current, exists=present):
        return 412
    if none_match is not None and not _if_none_match(none_match, current, exists=present):
        return 304 if verb in _SAFE_FOR_304 else 412
    return None
