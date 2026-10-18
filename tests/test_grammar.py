"""List grammar: commas, empty elements, whitespace, wildcard, obs-text, input forms."""

from __future__ import annotations

import pytest

from etag import EntityTag, is_wildcard, parse


@pytest.mark.parametrize("field", ['"a" "b"', '"a""b"', 'W/"a"W/"b"', '"a"\t"b"'])
def test_tags_must_be_separated_by_a_comma(field: str) -> None:
    with pytest.raises(ValueError, match="comma"):
        parse(field)


def test_empty_list_elements_are_skipped() -> None:
    assert parse(', "a" ,, "b",') == [EntityTag("a"), EntityTag("b")]


# Adapted from the RFC 9110 section 5.6.1.2 token examples by quoting each token.
@pytest.mark.parametrize(
    ("field", "values"),
    [
        ('"foo","bar"', ["foo", "bar"]),
        ('"foo" ,"bar",', ["foo", "bar"]),
        ('"foo" , ,"bar","charlie"', ["foo", "bar", "charlie"]),
    ],
)
def test_the_rfc_list_examples_are_accepted(field: str, values: list[str]) -> None:
    assert [tag.value for tag in parse(field)] == values


@pytest.mark.parametrize("field", ["", ",", ",   ,", " \t "])
def test_a_list_without_any_element_is_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="no entity-tag"):
        parse(field)


def test_spaces_and_tabs_around_the_value_are_ignored() -> None:
    assert parse(' \t"a"\t ') == [EntityTag("a")]


@pytest.mark.parametrize("field", ['\xa0"a"', '\v"a"', '"a"\n', '\r\n"a"', '"a"\x0c'])
def test_other_whitespace_is_not_optional_whitespace(field: str) -> None:
    with pytest.raises(ValueError):
        parse(field)


@pytest.mark.parametrize("field", ['*, "a"', '"a", *', "*,", ", *", "*, *", "**"])
def test_the_wildcard_only_stands_alone(field: str) -> None:
    with pytest.raises(ValueError):
        parse(field)
    assert is_wildcard(field) is False


@pytest.mark.parametrize("field", ['w/"a"', 'W/ "a"', "W/", 'W"a"', '/"a"'])
def test_the_weak_prefix_is_exact_and_case_sensitive(field: str) -> None:
    with pytest.raises(ValueError):
        parse(field)


def test_obs_text_is_allowed_inside_a_tag() -> None:
    assert parse('"\x80caf\xe9\xff"') == [EntityTag("\x80caf\xe9\xff")]


@pytest.mark.parametrize("char", ["\x00", "\x1f", " ", "\x7f", "Ā", "€"])
def test_characters_outside_etagc_are_rejected(char: str) -> None:
    with pytest.raises(ValueError, match="position 2"):
        parse(f'"a{char}"')


def test_the_wildcard_is_told_apart_from_the_star_tag() -> None:
    assert parse("*") == parse('"*"') == [EntityTag("*")]
    assert is_wildcard(" * ") is True
    assert is_wildcard('"*"') is False


def test_bytes_are_decoded_as_latin_1() -> None:
    assert parse(b'"caf\xe9", W/"b"') == [EntityTag("caf\xe9"), EntityTag("b", True)]
    assert parse(bytearray(b'"a"')) == [EntityTag("a")]
    assert parse(bytearray(b'"caf\xe9\xff"')) == [EntityTag("caf\xe9\xff")]
    lines: list[bytes | bytearray] = [b'"caf\xe9"', bytearray(b'W/"\x80\xff"')]
    assert parse(lines) == [EntityTag("caf\xe9"), EntityTag("\x80\xff", True)]


def test_field_lines_are_joined_in_order() -> None:
    assert parse(['"a"', b'W/"b"', ""]) == [EntityTag("a"), EntityTag("b", True)]
    assert is_wildcard(["*"]) is True


def test_field_lines_cannot_mix_the_wildcard_with_tags() -> None:
    with pytest.raises(ValueError):
        parse(["*", '"a"'])
    assert is_wildcard(["*", "*"]) is False


def test_blank_field_lines_are_dropped_before_joining() -> None:
    assert is_wildcard(["*", "", " 	"]) is True
    assert parse(["", '"a"', " "]) == [EntityTag("a")]


def test_no_field_lines_is_no_entity_tag() -> None:
    with pytest.raises(ValueError, match="no entity-tag"):
        parse([])


@pytest.mark.parametrize("header", [None, 3, ['"a"', 3], [None]])
def test_other_header_types_raise_type_error(header: object) -> None:
    with pytest.raises(TypeError):
        parse(header)  # type: ignore[arg-type]
