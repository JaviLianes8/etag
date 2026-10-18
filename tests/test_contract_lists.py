"""Contracts for list readings: empty lists, the wildcard among empty elements, positions."""

from __future__ import annotations

import pytest

from etag import (
    EntityTag,
    evaluate_preconditions,
    if_match,
    if_none_match,
    is_wildcard,
    matches,
    parse,
)

EMPTY_LISTS = ["", ",", " , ,", "\t,\t", b"", b" , ", [""], ["", " , "]]


@pytest.mark.parametrize("header", EMPTY_LISTS)
@pytest.mark.parametrize("weak", [True, False])
def test_matches_finds_no_member_in_a_list_with_no_element(
    header: str | bytes | list[str], weak: bool
) -> None:
    assert matches(header, '"a"', weak=weak) is False
    assert matches(header, 'W/"a"', weak=weak) is False


@pytest.mark.parametrize("header", EMPTY_LISTS)
def test_an_empty_list_agrees_with_the_evaluators_and_parse_still_rejects_it(
    header: str | bytes | list[str],
) -> None:
    assert if_match(header, '"a"') is False
    assert if_none_match(header, '"a"') is True
    with pytest.raises(ValueError, match="no entity-tag found"):
        parse(header)


@pytest.mark.parametrize(
    ("lines", "joined"),
    [(["*", ""], "*, "), (["", "*"], ", *"), (["*", " ", "\t"], "*, ,\t"), ([" * "], " , * ,")],
)
def test_the_wildcard_reads_the_same_as_field_lines_and_as_one_string(
    lines: list[str], joined: str
) -> None:
    for header in (lines, joined):
        assert is_wildcard(header) is True
        assert parse(header) == [EntityTag("*")]
        assert matches(header, '"zz"') is True
        assert if_none_match(header, '"a"') is False
        assert if_match(header, '"a"') is True
        assert evaluate_preconditions("GET", '"a"', if_none_match=header) == 304
        assert evaluate_preconditions("PUT", '"a"', if_none_match=header) == 412
        assert evaluate_preconditions("PUT", '"a"', if_match=header) is None
        assert evaluate_preconditions("PUT", None, if_match=header) == 412


@pytest.mark.parametrize("field", ['*, "a"', '"a", *', "*, *", "**", "*,*", '"*", *', "* *"])
def test_the_wildcard_never_mixes_with_other_members(field: str) -> None:
    assert is_wildcard(field) is False
    with pytest.raises(ValueError):
        parse(field)
    assert if_none_match(field, '"a"') is True
    assert if_match(field, '"a"') is False


def test_the_parsed_wildcard_equals_the_tag_star_by_design() -> None:
    # Kept from 0.2.0 so parse always returns EntityTag items; is_wildcard tells them apart.
    assert parse("*") == parse('"*"') == [EntityTag("*")]
    assert str(parse("*")[0]) == '"*"'
    assert is_wildcard("*") is True
    assert is_wildcard('"*"') is False
    assert if_match("*", None, exists=True) is True
    assert if_match('"*"', None, exists=True) is False


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (['"a"', '"b" x'], "expected a comma at position 9"),
        (['"a"', "W/x"], "expected an opaque-tag at position 7"),
        (['"a"', "", '"b" x'], "expected a comma at position 9"),
        ([b'"a"', b'"b\x7f"'], "invalid character in opaque-tag at position 7"),
        (['"a"', '"b'], "unterminated opaque-tag at position 5"),
    ],
)
def test_error_positions_count_in_the_lines_joined_with_comma_space(
    lines: list[str] | list[bytes], message: str
) -> None:
    with pytest.raises(ValueError, match=f"^{message}$"):
        parse(lines)
    with pytest.raises(ValueError, match=f"^{message}$"):
        matches(lines, '"a"')
