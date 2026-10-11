"""Compare entity-tags with the weak and strong rules of RFC 7232 section 2.3.2."""

from __future__ import annotations

from ._parse import WILDCARD, parse, parse_one


def matches(header: str, etag: str, *, weak: bool = True) -> bool:
    """Report whether ``etag`` satisfies a conditional request header.

    ``header`` is an ``If-None-Match`` or ``If-Match`` value and ``etag`` is a single
    entity-tag (as :func:`etag.make_etag` returns). With ``weak=True`` (the default,
    matching ``If-None-Match``) two tags are equivalent when their opaque values match,
    regardless of either being weak. With ``weak=False`` (matching ``If-Match``) both
    tags must be strong. A ``*`` wildcard header matches any tag.
    """
    if header.strip() == WILDCARD:
        return True
    target_value, target_weak = parse_one(etag)
    for value, is_weak in parse(header):
        if value != target_value:
            continue
        if weak or (not is_weak and not target_weak):
            return True
    return False
