"""If-Match, If-None-Match, If-Range and their precedence."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from etag import EntityTag, evaluate_preconditions, if_match, if_none_match, if_range

MALFORMED = ['"a" "b"', "a", "", ",", '*, "a"', 'w/"a"']


def test_if_match_uses_the_strong_comparison() -> None:
    assert if_match('"x", "a"', '"a"') is True
    assert if_match('"x", W/"a"', '"a"') is False
    assert if_match('"a"', EntityTag("a", True)) is False


@pytest.mark.parametrize("field", MALFORMED)
def test_a_malformed_if_match_is_false(field: str) -> None:
    assert if_match(field, '"a"') is False


def test_if_match_is_false_without_a_representation() -> None:
    assert if_match('"a"', None) is False
    assert if_match("*", None) is False
    assert if_match("*", '"a"') is True


def test_if_none_match_uses_the_weak_comparison() -> None:
    assert if_none_match('"x", W/"a"', '"a"') is False
    assert if_none_match('"x"', 'W/"a"') is True


@pytest.mark.parametrize("field", MALFORMED)
def test_a_malformed_if_none_match_is_true(field: str) -> None:
    assert if_none_match(field, '"a"') is True


def test_if_none_match_without_a_representation() -> None:
    assert if_none_match('"a"', None) is True
    assert if_none_match("*", None) is True
    assert if_none_match("*", '"a"') is False


def test_conditionals_take_bytes_and_field_lines() -> None:
    assert if_match([b'"x"', '"a"'], '"a"') is True
    assert if_none_match(['"x"', b'W/"a"'], '"a"') is False


@pytest.mark.parametrize("evaluator", [if_match, if_none_match, if_range])
def test_an_invalid_current_tag_is_a_programming_error(
    evaluator: Callable[[str, str], bool],
) -> None:
    with pytest.raises(ValueError):
        evaluator('"a"', "a")


def test_if_range_matches_only_an_identical_strong_tag() -> None:
    assert if_range('"a"', '"a"') is True
    assert if_range(b' "a" ', EntityTag("a")) is True
    assert if_range('"b"', '"a"') is False
    assert if_range('W/"a"', '"a"') is False
    assert if_range('"a"', 'W/"a"') is False
    assert if_range('"a"', None) is False


@pytest.mark.parametrize("field", ["Fri, 26 Mar 2010 00:05:00 GMT", '"a", "a"', "*", ""])
def test_if_range_is_false_for_anything_but_one_entity_tag(field: str) -> None:
    assert if_range(field, '"a"') is False


@pytest.mark.parametrize(
    ("method", "etag", "match", "none_match", "status"),
    [
        ("GET", '"a"', None, None, None),
        ("GET", '"a"', '"a"', '"x"', None),
        ("PUT", '"a"', '"b"', None, 412),
        ("GET", '"a"', '"b"', None, 412),
        ("GET", '"a"', '"b"', '"a"', 412),
        ("GET", '"a"', None, 'W/"a"', 304),
        ("HEAD", '"a"', '"a"', '"a"', 304),
        ("POST", '"a"', None, '"a"', 412),
        ("get", '"a"', None, '"a"', 412),
        ("PUT", None, None, "*", None),
        ("PUT", '"a"', None, "*", 412),
        ("PUT", None, "*", None, 412),
        ("DELETE", '"a"', "garbage", None, 412),
        ("GET", '"a"', None, "garbage", None),
    ],
)
def test_evaluate_preconditions_follows_section_13_2_2(
    method: str, etag: str | None, match: str | None, none_match: str | None, status: int | None
) -> None:
    result = evaluate_preconditions(method, etag, if_match=match, if_none_match=none_match)
    assert result == status


def test_evaluate_preconditions_validates_the_current_tag() -> None:
    with pytest.raises(ValueError):
        evaluate_preconditions("GET", "no quotes")


def test_an_empty_list_of_field_lines_means_the_field_is_absent() -> None:
    assert evaluate_preconditions("PUT", '"a"', if_match=[], if_none_match=[]) is None
    assert evaluate_preconditions("PUT", '"a"', if_match="") == 412


def test_blank_lines_do_not_hide_the_wildcard() -> None:
    assert if_none_match(["*", ""], '"a"') is False
    assert evaluate_preconditions("PUT", '"a"', if_none_match=["*", ""]) == 412


@pytest.mark.parametrize("method", ["CONNECT", "OPTIONS", "TRACE"])
def test_methods_without_a_representation_ignore_preconditions(method: str) -> None:
    assert evaluate_preconditions(method, '"a"', if_match='"b"', if_none_match="*") is None


@pytest.mark.parametrize("method", ["connect", "options", "trace", "Trace", "Options", "cONNECT"])
def test_only_the_upper_case_ignored_methods_skip_preconditions(method: str) -> None:
    # Method names are case-sensitive (RFC 9110 9.1): "trace" is some other method.
    assert evaluate_preconditions(method, '"a"', if_match='"b"') == 412
    assert evaluate_preconditions(method, '"a"', if_none_match='"a"') == 412


def test_a_resource_can_exist_without_an_entity_tag() -> None:
    assert if_match("*", None, exists=True) is True
    assert if_match('"a"', None, exists=True) is False
    assert if_none_match("*", None, exists=True) is False
    assert evaluate_preconditions("PUT", None, if_none_match="*", exists=True) == 412
    assert evaluate_preconditions("PUT", None, if_match="*", exists=True) is None


def test_exists_false_with_a_tag_is_rejected() -> None:
    with pytest.raises(ValueError, match="exists=False"):
        if_match("*", '"a"', exists=False)


@pytest.mark.parametrize(
    ("header", "status"),
    [((), None), ([], None), (None, None), ("", 412), (b"", 412), (bytearray(), 412)],
)
def test_only_none_and_empty_lists_are_absent_fields(header: object, status: int | None) -> None:
    assert evaluate_preconditions("PUT", '"b"', if_match=header) == status  # type: ignore[arg-type]
    # Present but empty, If-None-Match is true (no tag matches), so it never blocks.
    assert evaluate_preconditions("PUT", None, if_none_match=header) is None  # type: ignore[arg-type]
