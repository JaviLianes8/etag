"""Contracts for tag validation, case-sensitive values and the documented public types."""

from __future__ import annotations

import doctest
import inspect
import types
from collections.abc import Callable

import pytest

import etag
from etag import (
    EntityTag,
    evaluate_preconditions,
    if_match,
    if_none_match,
    if_range,
    matches,
    strong_compare,
    weak_compare,
)

BAD_VALUES = ['a"b', "a b", "\x00", "a\x7f", "\u0100", "\u20ac", ""[:0] + "\t"]
GOOD = EntityTag("ok")

CALLS: dict[str, Callable[[EntityTag], object]] = {
    "strong_compare left": lambda tag: strong_compare(tag, '"x"'),
    "strong_compare right": lambda tag: strong_compare('"x"', tag),
    "strong_compare both": lambda tag: strong_compare(tag, tag),
    "weak_compare left": lambda tag: weak_compare(tag, GOOD),
    "weak_compare right": lambda tag: weak_compare(GOOD, tag),
    "weak_compare both": lambda tag: weak_compare(tag, tag),
    "matches wildcard": lambda tag: matches("*", tag),
    "matches list": lambda tag: matches('"x"', tag, weak=False),
    "if_match wildcard": lambda tag: if_match("*", tag),
    "if_none_match wildcard": lambda tag: if_none_match("*", tag),
    "if_range": lambda tag: if_range('"x"', tag),
    "evaluate_preconditions": lambda tag: evaluate_preconditions("GET", tag),
    "evaluate_preconditions ignored method": lambda tag: evaluate_preconditions("TRACE", tag),
}


@pytest.mark.parametrize("value", BAD_VALUES)
@pytest.mark.parametrize("call", sorted(CALLS))
@pytest.mark.parametrize("weak", [False, True])
def test_a_malformed_entity_tag_object_is_rejected_everywhere(
    call: str, value: str, weak: bool
) -> None:
    with pytest.raises(ValueError, match="not allowed in an opaque-tag"):
        CALLS[call](EntityTag(value, weak))


def test_strong_and_weak_compare_are_case_sensitive() -> None:
    assert strong_compare('"A"', '"a"') is False
    assert strong_compare(EntityTag("aB"), EntityTag("Ab")) is False
    assert weak_compare('W/"A"', '"a"') is False
    assert strong_compare('"Ab"', '"Ab"') is True


@pytest.mark.parametrize("weak", [True, False])
def test_matches_compares_values_case_sensitively(weak: bool) -> None:
    assert matches('"A"', '"a"', weak=weak) is False
    assert matches('"x", "aB"', '"ab"', weak=weak) is False
    assert matches('"x", "aB"', '"aB"', weak=weak) is True


def test_the_evaluators_compare_values_case_sensitively() -> None:
    assert if_match('"A"', '"a"') is False
    assert if_match('"a"', '"a"') is True
    assert if_none_match('"A"', '"a"') is True
    assert if_none_match('W/"A"', '"a"') is True
    assert if_range('"A"', '"a"') is False
    assert if_range('"a"', '"a"') is True
    assert evaluate_preconditions("PUT", '"a"', if_match='"A"') == 412
    assert evaluate_preconditions("GET", '"a"', if_none_match='"A"') is None


def test_entity_tag_shows_a_plain_signature() -> None:
    assert str(inspect.signature(EntityTag)) == "(value: str, weak: bool = False)"
    assert EntityTag.__annotations__ == {"value": str, "weak": bool}


def test_header_is_the_only_type_alias_and_the_package_documents_it() -> None:
    aliases = {name for name in etag.__all__ if isinstance(getattr(etag, name), types.UnionType)}
    assert aliases == {"Header"}
    assert etag.__doc__ is not None
    assert ":data:`Header`" in etag.__doc__
    parsed = doctest.DocTestParser().get_examples(etag.__doc__)
    assert any("Header" in example.source for example in parsed)
