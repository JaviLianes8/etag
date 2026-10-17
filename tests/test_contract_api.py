"""The 1.0.0 API contract: signatures, module names, option types and error types."""

from __future__ import annotations

import inspect
import pickle
from collections.abc import Callable
from typing import Any

import pytest

import etag
from etag import (
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
)

K, P = "KEYWORD_ONLY", "POSITIONAL_OR_KEYWORD"
SIGNATURES: dict[str, list[tuple[str, str, object]]] = {
    "EntityTag": [("value", P, inspect.Parameter.empty), ("weak", P, False)],
    "evaluate_preconditions": [
        ("method", P, inspect.Parameter.empty),
        ("etag", P, inspect.Parameter.empty),
        ("if_match", K, None),
        ("if_none_match", K, None),
        ("exists", K, None),
    ],
    "format_etag": [("value", P, inspect.Parameter.empty), ("weak", K, False)],
    "if_match": [("header", P, inspect.Parameter.empty), ("etag", P, inspect.Parameter.empty)]
    + [("exists", K, None)],
    "if_none_match": [("header", P, inspect.Parameter.empty)]
    + [("etag", P, inspect.Parameter.empty), ("exists", K, None)],
    "if_range": [("header", P, inspect.Parameter.empty), ("etag", P, inspect.Parameter.empty)],
    "is_wildcard": [("header", P, inspect.Parameter.empty)],
    "make_etag": [("data", P, inspect.Parameter.empty), ("weak", K, False)],
    "matches": [("header", P, inspect.Parameter.empty), ("etag", P, inspect.Parameter.empty)]
    + [("weak", K, True)],
    "parse": [("header", P, inspect.Parameter.empty)],
    "strong_compare": [("a", P, inspect.Parameter.empty), ("b", P, inspect.Parameter.empty)],
    "weak_compare": [("a", P, inspect.Parameter.empty), ("b", P, inspect.Parameter.empty)],
}


@pytest.mark.parametrize("name", sorted(SIGNATURES))
def test_signatures_are_frozen(name: str) -> None:
    params = inspect.signature(getattr(etag, name)).parameters.values()
    assert [(p.name, p.kind.name, p.default) for p in params] == SIGNATURES[name]


def test_the_module_exposes_nothing_public_beyond_all() -> None:
    public = {name for name in dir(etag) if not name.startswith("_")}
    assert public == set(etag.__all__)
    assert set(SIGNATURES) == set(etag.__all__) - {"Header"}


@pytest.mark.parametrize("name", sorted(SIGNATURES))
def test_public_names_report_the_package_as_their_module(name: str) -> None:
    assert getattr(etag, name).__module__ == "etag"


def test_entity_tags_pickle_and_print() -> None:
    tag = EntityTag("a", True)
    assert pickle.loads(pickle.dumps(tag)) == tag
    assert repr(tag) == "EntityTag(value='a', weak=True)"


FLAG_CALLS: list[Callable[[Any], object]] = [
    lambda flag: format_etag("a", weak=flag),
    lambda flag: make_etag(b"a", weak=flag),
    lambda flag: matches('"a"', '"a"', weak=flag),
    lambda flag: str(EntityTag("a", flag)),
    lambda flag: strong_compare(EntityTag("a", flag), '"a"'),
    lambda flag: weak_compare('"a"', EntityTag("a", flag)),
    lambda flag: if_match("*", '"a"', exists=flag),
    lambda flag: if_none_match("*", '"a"', exists=flag),
    lambda flag: evaluate_preconditions("GET", '"a"', exists=flag),
]


@pytest.mark.parametrize("flag", [0, 1, "yes", "", 1.0, [True]])
@pytest.mark.parametrize("call", FLAG_CALLS)
def test_options_must_be_real_bools(call: Callable[[Any], object], flag: object) -> None:
    with pytest.raises(TypeError, match="must be a bool"):
        call(flag)


@pytest.mark.parametrize("method", [b"GET", None, 1, ["GET"]])
def test_the_method_must_be_text(method: object) -> None:
    with pytest.raises(TypeError, match="method must be a str"):
        evaluate_preconditions(method, '"a"')  # type: ignore[arg-type]


@pytest.mark.parametrize("header", [0, False, 1.5, {}, {"a": 1}, object(), [1], [None]])
def test_a_header_of_another_type_raises_type_error(header: object) -> None:
    for call in (parse, is_wildcard, lambda h: if_match(h, '"a"'), lambda h: if_range(h, None)):
        with pytest.raises(TypeError):
            call(header)
    with pytest.raises(TypeError):
        evaluate_preconditions("GET", '"a"', if_match=header)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        evaluate_preconditions("OPTIONS", None, if_none_match=header)  # type: ignore[arg-type]


@pytest.mark.parametrize("etag_value", [b'"a"', 1, None, ("a", False)])
def test_a_tag_of_another_type_raises_type_error(etag_value: object) -> None:
    with pytest.raises(TypeError):
        strong_compare(etag_value, '"a"')  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        matches('"a"', etag_value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [1, None, b"a", ["a"]])
def test_an_entity_tag_value_that_is_not_text_raises_type_error(value: object) -> None:
    with pytest.raises(TypeError):
        str(EntityTag(value, False))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        if_match('"a"', EntityTag(value, False))  # type: ignore[arg-type]


def test_make_etag_hashes_any_contiguous_buffer() -> None:
    import array

    assert make_etag(array.array("B", b"abc")) == make_etag(b"abc")  # type: ignore[arg-type]
    for bad in (1, None, ["a"], 1.5):
        with pytest.raises(TypeError, match="bytes-like or str"):
            make_etag(bad)  # type: ignore[arg-type]
    with pytest.raises(UnicodeEncodeError):
        make_etag("\ud800")


def test_matches_rejects_a_malformed_list_whatever_the_target() -> None:
    with pytest.raises(ValueError):
        matches('"a" "b"', 'W/"a"', weak=False)
    with pytest.raises(ValueError):
        matches("", 'W/"a"', weak=False)


def test_exists_false_with_a_tag_is_a_value_error() -> None:
    for call in (if_match, if_none_match):
        with pytest.raises(ValueError, match="exists=False"):
            call("*", '"a"', exists=False)
    with pytest.raises(ValueError, match="exists=False"):
        evaluate_preconditions("GET", '"a"', exists=False)
