"""Create, parse and compare HTTP entity-tags and evaluate conditional requests (RFC 9110).

Every header argument is a :data:`Header`: text, Latin-1 bytes, or a list of field
lines, which are joined in order with a comma. ``Header`` is a type alias for
annotating your own code, so this paragraph is its documentation; the three forms
below carry the same field value.

>>> from etag import Header, parse
>>> forms: list[Header] = ['"a", W/"b"', b'"a", W/"b"', ['"a"', b'W/"b"']]
>>> [parse(form) == [("a", False), ("b", True)] for form in forms]
[True, True, True]

>>> from etag import evaluate_preconditions, make_etag
>>> current = make_etag(b"<h1>Hello</h1>")
>>> evaluate_preconditions("GET", current, if_none_match=[b'"old"', current])
304
"""

from ._compare import matches, strong_compare, weak_compare
from ._conditional import evaluate_preconditions, if_match, if_none_match, if_range
from ._parse import Header, is_wildcard, parse
from ._tag import EntityTag, format_etag, make_etag

__version__ = "1.0.0"

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

# Public names report the package, not the private module that happens to define them.
for _public in (
    EntityTag,
    evaluate_preconditions,
    format_etag,
    if_match,
    if_none_match,
    if_range,
    is_wildcard,
    make_etag,
    matches,
    parse,
    strong_compare,
    weak_compare,
):
    _public.__module__ = __name__
del _public
