"""strong_compare, weak_compare and matches beyond the RFC table."""

from __future__ import annotations

import pytest

from etag import EntityTag, matches, strong_compare, weak_compare


def test_comparisons_take_entity_tag_values() -> None:
    assert strong_compare(EntityTag("a"), '"a"') is True
    assert weak_compare(EntityTag("a", True), EntityTag("a")) is True


def test_comparisons_are_character_by_character() -> None:
    assert weak_compare('"a"', '"A"') is False
    assert strong_compare('"caf\xe9"', '"cafe"') is False


@pytest.mark.parametrize("bad", ['"a", "b"', '"a",', "*", "a", ""])
def test_comparisons_reject_anything_but_one_entity_tag(bad: str) -> None:
    with pytest.raises(ValueError):
        strong_compare(bad, '"a"')
    with pytest.raises(ValueError):
        weak_compare('"a"', bad)


def test_matches_validates_the_tag_even_for_the_wildcard() -> None:
    with pytest.raises(ValueError):
        matches("*", "not quoted")


def test_matches_reads_field_lines_and_bytes() -> None:
    assert matches([b'"x"', 'W/"a"'], '"a"') is True
    assert matches([b'"x"', 'W/"a"'], '"a"', weak=False) is False


def test_matches_raises_on_a_malformed_header() -> None:
    with pytest.raises(ValueError):
        matches('"a" "b"', '"a"')


def test_matches_with_a_weak_target_never_matches_strongly() -> None:
    assert matches('"a", W/"a"', 'W/"a"', weak=False) is False
    assert matches('"x", W/"a"', 'W/"a"') is True
