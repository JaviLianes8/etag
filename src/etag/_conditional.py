"""Evaluate conditional requests on entity-tags (RFC 9110 sections 13.1 and 13.2)."""

from __future__ import annotations

from typing import Literal

from ._compare import strong_compare, weak_compare
from ._parse import Header, field_value, is_wildcard, parse, parse_one
from ._tag import EntityTag

_SAFE_FOR_304 = ("GET", "HEAD")


def _current(etag: str | EntityTag | None) -> EntityTag | None:
    return None if etag is None else parse_one(etag)


def if_match(header: Header, etag: str | EntityTag | None) -> bool:
    """Evaluate an If-Match field value against the current entity-tag (13.1.1).

    ``etag`` is the selected representation's entity-tag, or ``None`` when the
    resource has no current representation. ``*`` is true when one exists; a list is
    true when a member matches with the strong comparison; anything else, including a
    malformed value, is false. A false result means "respond 412".
    """
    current = _current(etag)
    if is_wildcard(header):
        return current is not None
    try:
        tags = parse(header)
    except ValueError:
        return False
    return current is not None and any(strong_compare(tag, current) for tag in tags)


def if_none_match(header: Header, etag: str | EntityTag | None) -> bool:
    """Evaluate an If-None-Match field value against the current entity-tag (13.1.2).

    ``etag`` is the selected representation's entity-tag, or ``None`` when the
    resource has no current representation. ``*`` is false when one exists; a list is
    false when a member matches with the weak comparison; anything else, including a
    malformed value, is true. A false result means 304 for GET and HEAD, 412 otherwise.
    """
    current = _current(etag)
    if is_wildcard(header):
        return current is None
    try:
        tags = parse(header)
    except ValueError:
        return True
    return current is None or not any(weak_compare(tag, current) for tag in tags)


def if_range(header: Header, etag: str | EntityTag | None) -> bool:
    """Evaluate an entity-tag If-Range field value (13.1.5).

    True only when the value is a single entity-tag that matches ``etag`` with the
    strong comparison, so a weak tag never matches. An HTTP-date, a list or a malformed
    value is false here: evaluate the date form yourself before calling this. A false
    result means "ignore Range and send the whole representation".
    """
    current = _current(etag)
    try:
        candidate = parse_one(field_value(header))
    except ValueError:
        return False
    return current is not None and strong_compare(candidate, current)


# The keyword arguments below shadow the evaluators, so keep a reference to each.
_if_match = if_match
_if_none_match = if_none_match


def evaluate_preconditions(
    method: str,
    etag: str | EntityTag | None,
    *,
    if_match: Header | None = None,
    if_none_match: Header | None = None,
) -> Literal[304, 412] | None:
    """Return the status a precondition failure demands, or ``None`` to proceed.

    Follows the order of section 13.2.2 for the entity-tag fields of an origin server:
    If-Match first (412 when false), then If-None-Match (304 for ``GET`` and ``HEAD``,
    412 for other methods; method names are case-sensitive). Pass ``None`` for a field
    the request did not carry. If you also support dates, check If-Unmodified-Since
    only when ``if_match`` is ``None`` and If-Modified-Since only when
    ``if_none_match`` is ``None``.
    """
    current = _current(etag)
    if if_match is not None and not _if_match(if_match, current):
        return 412
    if if_none_match is not None and not _if_none_match(if_none_match, current):
        return 304 if method in _SAFE_FOR_304 else 412
    return None
