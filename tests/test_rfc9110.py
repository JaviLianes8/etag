"""Ground truth copied from RFC 9110 as fetched on 2026-10-12.

Source: https://www.rfc-editor.org/rfc/rfc9110.txt (sha256 of the fetched file
21c1cdce6ab0e5509b04d84a28000836c7a087cf786efe6f04877ebfff47232a). Every field value
below is copied character for character from the section named next to it.
"""

from __future__ import annotations

import pytest

from etag import (
    EntityTag,
    if_match,
    if_none_match,
    is_wildcard,
    parse,
    strong_compare,
    weak_compare,
)

# Section 3.9 example message exchange, then section 8.8.3 "Examples:".
ETAG_EXAMPLES = [
    ('"34aa387-d-1568eb00"', EntityTag("34aa387-d-1568eb00", False)),
    ('"xyzzy"', EntityTag("xyzzy", False)),
    ('W/"xyzzy"', EntityTag("xyzzy", True)),
    ('""', EntityTag("", False)),
    # Section 8.8.3.3, the two representations of one negotiated resource.
    ('"123-a"', EntityTag("123-a", False)),
    ('"123-b"', EntityTag("123-b", False)),
]

# Section 8.8.3.2, Table 3: ETag 1, ETag 2, strong comparison, weak comparison.
TABLE_3 = [
    ('W/"1"', 'W/"1"', "no match", "match"),
    ('W/"1"', 'W/"2"', "no match", "no match"),
    ('W/"1"', '"1"', "no match", "match"),
    ('"1"', '"1"', "match", "match"),
]

# Section 13.1.1 If-Match "Examples:".
IF_MATCH_EXAMPLES = [
    '"xyzzy"',
    '"xyzzy", "r2d2xxxx", "c3piozzzz"',
    "*",
]

# Section 13.1.2 If-None-Match "Examples:".
IF_NONE_MATCH_EXAMPLES = [
    '"xyzzy"',
    'W/"xyzzy"',
    '"xyzzy", "r2d2xxxx", "c3piozzzz"',
    'W/"xyzzy", W/"r2d2xxxx", W/"c3piozzzz"',
    "*",
]


@pytest.mark.parametrize(("field", "expected"), ETAG_EXAMPLES)
def test_every_etag_example_parses_and_serialises_back(field: str, expected: EntityTag) -> None:
    assert parse(field) == [expected]
    assert str(expected) == field


@pytest.mark.parametrize(("one", "two", "strong", "weak"), TABLE_3)
def test_table_3_comparisons_in_both_orders(one: str, two: str, strong: str, weak: str) -> None:
    assert strong_compare(one, two) is (strong == "match")
    assert strong_compare(two, one) is (strong == "match")
    assert weak_compare(one, two) is (weak == "match")
    assert weak_compare(two, one) is (weak == "match")


@pytest.mark.parametrize("field", IF_MATCH_EXAMPLES + IF_NONE_MATCH_EXAMPLES)
def test_every_conditional_example_parses(field: str) -> None:
    tags = parse(field)
    assert is_wildcard(field) is (field == "*")
    assert len(tags) == field.count('"') // 2 or field == "*"


def test_if_match_examples_are_true_for_xyzzy() -> None:
    for field in IF_MATCH_EXAMPLES:
        assert if_match(field, '"xyzzy"') is True


def test_if_match_examples_are_false_for_a_weak_xyzzy() -> None:
    # The strong comparison is mandatory for If-Match; only "*" still holds.
    assert [if_match(field, 'W/"xyzzy"') for field in IF_MATCH_EXAMPLES] == [False, False, True]


def test_if_none_match_examples_are_false_for_xyzzy_weak_or_strong() -> None:
    for field in IF_NONE_MATCH_EXAMPLES:
        assert if_none_match(field, '"xyzzy"') is False
        assert if_none_match(field, 'W/"xyzzy"') is False


def test_if_none_match_examples_are_true_for_another_tag() -> None:
    results = [if_none_match(field, '"other"') for field in IF_NONE_MATCH_EXAMPLES]
    assert results == [True, True, True, True, False]


def test_the_wildcard_depends_only_on_a_current_representation() -> None:
    assert if_match("*", None) is False
    assert if_none_match("*", None) is True
