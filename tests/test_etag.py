import pytest

from etag import make_etag, matches, parse


def test_make_etag_is_strong_and_quoted_by_default() -> None:
    tag = make_etag(b"body")
    assert tag.startswith('"') and tag.endswith('"')
    assert not tag.startswith("W/")


def test_make_etag_adds_the_weak_prefix() -> None:
    assert make_etag(b"body", weak=True).startswith('W/"')


def test_make_etag_treats_text_as_its_utf8_bytes() -> None:
    assert make_etag("body") == make_etag(b"body")


def test_make_etag_differs_for_different_data() -> None:
    assert make_etag(b"one") != make_etag(b"two")


def test_make_etag_round_trips_through_parse() -> None:
    value, weak = parse(make_etag(b"body", weak=True))[0]
    assert weak is True
    assert value == parse(make_etag(b"body"))[0][0]


def test_parse_reads_a_single_strong_tag() -> None:
    assert parse('"abc"') == [("abc", False)]


def test_parse_reads_a_weak_tag() -> None:
    assert parse('W/"abc"') == [("abc", True)]


def test_parse_reads_multiple_tags() -> None:
    assert parse('"a", W/"b" , "c"') == [("a", False), ("b", True), ("c", False)]


def test_parse_keeps_a_comma_inside_the_opaque_tag() -> None:
    assert parse('"a,b", "c"') == [("a,b", False), ("c", False)]


def test_parse_reads_the_wildcard() -> None:
    assert parse("*") == [("*", False)]


def test_parse_rejects_an_unquoted_tag() -> None:
    with pytest.raises(ValueError):
        parse("abc")


def test_parse_rejects_an_unterminated_tag() -> None:
    with pytest.raises(ValueError):
        parse('"abc')


def test_parse_rejects_a_space_in_the_opaque_tag() -> None:
    with pytest.raises(ValueError):
        parse('"a b"')


def test_parse_rejects_an_empty_header() -> None:
    with pytest.raises(ValueError):
        parse("   ")


def test_matches_finds_a_strong_tag_in_the_list() -> None:
    assert matches('"a", "b", "c"', '"b"') is True


def test_matches_returns_false_when_absent() -> None:
    assert matches('"a", "b"', '"z"') is False


def test_matches_wildcard_matches_any_tag() -> None:
    assert matches("*", '"anything"') is True


def test_weak_comparison_ignores_the_weak_flag() -> None:
    assert matches('W/"a"', '"a"') is True
    assert matches('"a"', 'W/"a"') is True


def test_strong_comparison_rejects_a_weak_header_tag() -> None:
    assert matches('W/"a"', '"a"', weak=False) is False


def test_strong_comparison_rejects_a_weak_target() -> None:
    assert matches('"a"', 'W/"a"', weak=False) is False


def test_strong_comparison_accepts_two_strong_tags() -> None:
    assert matches('"a"', '"a"', weak=False) is True


def test_matches_rejects_a_list_as_the_target() -> None:
    with pytest.raises(ValueError):
        matches('"a"', '"a", "b"')


def test_matches_rejects_the_wildcard_as_the_target() -> None:
    with pytest.raises(ValueError):
        matches('"a"', "*")
