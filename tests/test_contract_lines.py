"""Contracts for field lines: what counts as blank, where lines start, how many are read."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from etag import (
    EntityTag,
    evaluate_preconditions,
    if_match,
    if_none_match,
    if_range,
    is_wildcard,
    parse,
)

Line = str | bytes | bytearray
KINDS: dict[str, Callable[[str], Line]] = {
    "str": lambda line: line,
    "latin-1 bytes": lambda line: line.encode("latin-1"),
    "bytearray": lambda line: bytearray(line.encode("latin-1")),
}
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


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("blank", [[""], ["  "], ["\t"], ["", " \t "]])
def test_a_list_of_blank_lines_is_a_field_sent_with_an_empty_value(
    blank: list[str], kind: str
) -> None:
    # Only an empty list means the field was not sent; blank lines are an empty value,
    # which no current tag matches.
    lines = [KINDS[kind](line) for line in blank]
    assert evaluate_preconditions("PUT", '"a"', if_match=lines) == 412
    assert evaluate_preconditions("PUT", None, if_match=lines) == 412
    assert evaluate_preconditions("PUT", '"a"', if_match=[]) is None
    assert if_match(lines, '"a"') is False
    # An If-None-Match with no member is true, so it proceeds as an absent one does.
    assert evaluate_preconditions("GET", '"a"', if_none_match=lines) is None
    assert evaluate_preconditions("PUT", '"a"', if_none_match=lines) is None
    assert if_none_match(lines, '"a"') is True


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("first", ["", " ", "\t", " \t "])
def test_a_blank_first_line_is_dropped(first: str, kind: str) -> None:
    line = KINDS[kind]
    assert if_range([line(first), line('"a"')], '"a"') is True
    assert if_range([line(first), line('"a"'), line(first)], '"a"') is True
    assert if_match([line('"a"'), line(first)], '"a"') is True
    assert parse([line(first), line('W/"b"')]) == [EntityTag("b", weak=True)]
    with pytest.raises(ValueError, match=r"^expected an opaque-tag at position 0$"):
        parse([line(first), line("x")])


def test_every_field_line_is_read_however_many_there_are() -> None:
    # Well past any round cap a reader might put on the number of lines.
    lines = ['""'] * 100_000 + ['"a"']
    assert if_match(lines, '"a"') is True
    assert if_none_match(lines, '"a"') is False
    assert evaluate_preconditions("GET", '"a"', if_none_match=lines) == 304
    assert parse(lines)[-1] == EntityTag("a")
    assert len(parse(lines)) == 100_001


@pytest.mark.parametrize("blank", ["", " ", "\t"])
def test_thousands_of_blank_lines_before_the_last_one_are_all_dropped(blank: str) -> None:
    lines = [blank] * 100_000
    assert if_match([*lines, '"a"'], '"a"') is True
    assert if_range([*lines, '"a"'], '"a"') is True
    assert is_wildcard([*lines, "*"]) is True
    with pytest.raises(ValueError, match=r"^expected an opaque-tag at position 0$"):
        parse([*lines, "x"])
    with pytest.raises(ValueError, match=r"^expected a comma at position 4$"):
        parse([*lines, '"a" x'])
