"""Contracts for field lines: what counts as blank, where lines start, how many are read."""

from __future__ import annotations

import pytest

from etag import EntityTag, evaluate_preconditions, if_match, if_none_match, if_range, parse

NOT_BLANK = ["\x0b", "\x0c", "\r", "\xa0", " \x0b ", "\t\x0c"]


@pytest.mark.parametrize("encode", [False, True], ids=["str", "latin-1 bytes"])
@pytest.mark.parametrize("line", NOT_BLANK)
def test_a_line_with_whitespace_other_than_space_and_tab_is_not_blank(
    line: str, encode: bool
) -> None:
    # Only spaces and tabs are optional whitespace (section 5.6.3), so such a line is a
    # malformed element, never a dropped blank line.
    lines: list[str] | list[bytes] = [b'"a"', line.encode("latin-1")] if encode else ['"a"', line]
    with pytest.raises(ValueError, match=r"^expected an opaque-tag at position \d+$"):
        parse(lines)
    assert if_none_match(lines, '"a"') is True
    assert if_match(lines, '"a"') is False
    assert evaluate_preconditions("GET", '"a"', if_none_match=lines) is None


@pytest.mark.parametrize("lines", [[""], ["  "], ["\t"], ["", " \t "]])
def test_a_list_of_blank_lines_is_a_field_sent_with_an_empty_value(lines: list[str]) -> None:
    # Only an empty list means the field was not sent; blank lines are an empty value,
    # which no current tag matches.
    assert evaluate_preconditions("PUT", '"a"', if_match=lines) == 412
    assert evaluate_preconditions("PUT", None, if_match=lines) == 412
    assert evaluate_preconditions("PUT", '"a"', if_match=[]) is None
    assert if_match(lines, '"a"') is False
    # An If-None-Match with no member is true, so it proceeds as an absent one does.
    assert evaluate_preconditions("GET", '"a"', if_none_match=lines) is None
    assert evaluate_preconditions("PUT", '"a"', if_none_match=lines) is None
    assert if_none_match(lines, '"a"') is True


@pytest.mark.parametrize("first", ["", " ", "\t", " \t "])
def test_a_blank_first_line_is_dropped(first: str) -> None:
    assert if_range([first, '"a"'], '"a"') is True
    assert if_range([first, '"a"', first], '"a"') is True
    assert parse([first, 'W/"b"']) == [EntityTag("b", weak=True)]
    with pytest.raises(ValueError, match=r"^expected an opaque-tag at position 0$"):
        parse([first, "x"])


def test_every_field_line_is_read_however_many_there_are() -> None:
    lines = ['""'] * 1000 + ['"a"']
    assert if_match(lines, '"a"') is True
    assert if_none_match(lines, '"a"') is False
    assert evaluate_preconditions("GET", '"a"', if_none_match=lines) == 304
    assert parse(lines)[-1] == EntityTag("a")
    assert len(parse(lines)) == 1001
