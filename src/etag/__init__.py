"""Create, parse and compare HTTP entity-tags and evaluate conditional requests (RFC 9110)."""

from __future__ import annotations

from ._compare import matches, strong_compare, weak_compare
from ._conditional import evaluate_preconditions, if_match, if_none_match, if_range
from ._parse import Header, is_wildcard, parse
from ._tag import EntityTag, format_etag, make_etag

__version__ = "0.2.0"

__all__ = [
    "EntityTag",
    "Header",
    "evaluate_preconditions",
    "format_etag",
    "if_match",
    "if_none_match",
    "if_range",
    "is_wildcard",
    "make_etag",
    "matches",
    "parse",
    "strong_compare",
    "weak_compare",
]
