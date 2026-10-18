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

K, P, E = "KEYWORD_ONLY", "POSITIONAL_OR_KEYWORD", inspect.Parameter.empty
SIGNATURES: dict[str, list[tuple[str, str, object]]] = {
    "EntityTag": [("value", P, E), ("weak", P, False)],
    "evaluate_preconditions": [
        ("method", P, E),
        ("etag", P, E),
        ("if_match", K, None),
        ("if_none_match", K, None),
        ("exists", K, None),
    ],
    "format_etag": [("value", P, E), ("weak", K, False)],
    "if_match": [("header", P, E), ("etag", P, E), ("exists", K, None)],
    "if_none_match": [("header", P, E), ("etag", P, E), ("exists", K, None)],
    "if_range": [("header", P, E), ("etag", P, E)],
    "is_wildcard": [("header", P, E)],
    "make_etag": [("data", P, E), ("weak", K, False)],
    "matches": [("header", P, E), ("etag", P, E), ("weak", K, True)],
    "parse": [("header", P, E)],
    "strong_compare": [("a", P, E), ("b", P, E)],
    "weak_compare": [("a", P, E), ("b", P, E)],
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
    calls: list[Callable[[Any], object]] = [parse, is_wildcard]
    calls += [lambda h: if_match(h, '"a"'), lambda h: if_range(h, None)]
    for call in calls:
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
    with pytest.raises(ValueError) as caught:
        make_etag("secret\ud800")
    assert str(caught.value) == "U+D800 cannot be encoded as UTF-8 at 6"
    assert not isinstance(caught.value, UnicodeError)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    # A run of surrogates is reported at its first one.
    with pytest.raises(ValueError, match=r"^U\+D800 cannot be encoded as UTF-8 at 0$"):
        make_etag("\ud800\udbff")


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


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: format_etag("ab c"), "U+0020 is not allowed in an opaque-tag at 2"),
        (lambda: parse(' "a" x'), "expected a comma at position 5"),
        (lambda: parse('"a", b'), "expected an opaque-tag at position 5"),
        (lambda: parse('  W/"ab'), "unterminated opaque-tag at position 4"),
        (lambda: parse('"a"'), "invalid character in opaque-tag at position 2"),
        (lambda: parse(" , "), "no entity-tag found"),
        (
            lambda: strong_compare(' "a" "b"', '"a"'),
            "expected a single entity-tag, more at position 4",
        ),
    ],
)
def test_error_messages_give_the_documented_positions(
    call: Callable[[], object], message: str
) -> None:
    with pytest.raises(ValueError) as caught:
        call()
    assert str(caught.value) == message
