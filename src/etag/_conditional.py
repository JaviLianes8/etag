"""Evaluate conditional requests on entity-tags (RFC 9110 sections 13.1 and 13.2)."""

from __future__ import annotations

from typing import Literal

from ._parse import Header, field_value, is_wildcard, parse, parse_one
from ._tag import EntityTag

_SAFE_FOR_304 = ("GET", "HEAD")
# Section 13.2.1: these methods do not select a representation, so they ignore the fields.
_IGNORE_PRECONDITIONS = ("CONNECT", "OPTIONS", "TRACE")


def _state(etag: str | EntityTag | None, exists: bool | None) -> tuple[EntityTag | None, bool]:
    """Validate the current tag and decide whether a current representation exists."""
    current = None if etag is None else parse_one(etag)
    if exists is None:
        return current, current is not None
    if not exists and current is not None:
        raise ValueError("exists=False contradicts a current entity-tag")
    return current, exists


def if_match(header: Header, etag: str | EntityTag | None, *, exists: bool | None = None) -> bool:
    """Evaluate an If-Match field value against the current entity-tag (13.1.1).

    ``etag`` is the selected representation's entity-tag, or ``None`` when there is
    none. ``exists`` says whether a current representation exists; it defaults to
    ``etag is not None`` and only needs passing for a resource served without a tag.
    ``*`` is true when one exists; a list is true when a member matches with the strong
    comparison; anything else, including a malformed value, is false. A false result
    means "respond 412".
    """
    current, present = _state(etag, exists)
    if is_wildcard(header):
        return present
    try:
        tags = parse(header)
    except ValueError:
        return False
    if current is None or current.weak:
        return False
    return any(not tag.weak and tag.value == current.value for tag in tags)


def if_none_match(
    header: Header, etag: str | EntityTag | None, *, exists: bool | None = None
) -> bool:
    """Evaluate an If-None-Match field value against the current entity-tag (13.1.2).

    ``etag`` and ``exists`` work as in :func:`if_match`. ``*`` is false when a current
    representation exists; a list is false when a member matches with the weak
    comparison; anything else, including a malformed value, is true. A false result
    means 304 for GET and HEAD, 412 otherwise.
    """
    current, present = _state(etag, exists)
    if is_wildcard(header):
        return not present
    try:
        tags = parse(header)
    except ValueError:
        return True
    if current is None:
        return True
    return not any(tag.value == current.value for tag in tags)


def if_range(header: Header, etag: str | EntityTag | None) -> bool:
    """Evaluate an entity-tag If-Range field value (13.1.5).

    True only when the value is a single entity-tag that matches ``etag`` with the
    strong comparison, so a weak tag never matches. An HTTP-date, a list or a malformed
    value is false here: evaluate the date form yourself before calling this. A false
    result means "ignore Range and send the whole representation".
    """
    current, _ = _state(etag, None)
    try:
        candidate = parse_one(field_value(header))
    except ValueError:
        return False
    if current is None or current.weak or candidate.weak:
        return False
    return candidate.value == current.value


def _absent(header: Header | None) -> bool:
    # A framework's getlist() returns [] for a field the request did not carry.
    return header is None or (not isinstance(header, (str, bytes, bytearray)) and not header)


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
    and ``TRACE`` ignore both fields (13.2.1). Pass ``None`` or an empty list for a
    field the request did not carry; ``exists`` works as in :func:`if_match`. If you
    also support dates, check If-Unmodified-Since only when If-Match is absent and
    If-Modified-Since only when If-None-Match is absent.
    """
    current, present = _state(etag, exists)
    if method in _IGNORE_PRECONDITIONS:
        return None
    if not _absent(if_match) and not _if_match(if_match or "", current, exists=present):
        return 412
    if not _absent(if_none_match) and not _if_none_match(
        if_none_match or "", current, exists=present
    ):
        return 304 if method in _SAFE_FOR_304 else 412
    return None
