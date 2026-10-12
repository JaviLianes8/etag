"""The EntityTag value type, format_etag and make_etag."""

from __future__ import annotations

import hashlib

import pytest

from etag import EntityTag, format_etag, make_etag, parse


def test_entity_tag_unpacks_and_compares_as_a_tuple() -> None:
    value, weak = EntityTag("a", True)
    assert (value, weak) == ("a", True)
    assert EntityTag("a") == ("a", False)


def test_entity_tag_serialises_to_the_header_form() -> None:
    assert str(EntityTag("a")) == '"a"'
    assert str(EntityTag("a", weak=True)) == 'W/"a"'


@pytest.mark.parametrize("value", ['a"b', "a b", "a\r\nSet-Cookie: x", "Ā"])
def test_entity_tag_refuses_to_serialise_an_invalid_value(value: str) -> None:
    with pytest.raises(ValueError):
        str(EntityTag(value))


def test_format_etag_quotes_a_server_chosen_value() -> None:
    assert format_etag("123-a") == '"123-a"'
    assert format_etag("123-a", weak=True) == 'W/"123-a"'
    assert format_etag("") == '""'


def test_format_etag_round_trips_every_etagc_character() -> None:
    value = "".join(chr(c) for c in [0x21, *range(0x23, 0x7F), *range(0x80, 0x100)])
    assert parse(format_etag(value, weak=True)) == [EntityTag(value, True)]


@pytest.mark.parametrize("value", ['"', "a b", "\t", "\x7f", "Ā"])
def test_format_etag_rejects_characters_outside_etagc(value: str) -> None:
    with pytest.raises(ValueError):
        format_etag(value)


def test_format_etag_rejects_non_text() -> None:
    with pytest.raises(TypeError):
        format_etag(b"abc")  # type: ignore[arg-type]


def test_make_etag_is_the_sha256_of_the_content() -> None:
    assert make_etag(b"abc") == '"' + hashlib.sha256(b"abc").hexdigest() + '"'


def test_make_etag_accepts_every_bytes_like_form() -> None:
    expected = make_etag(b"body")
    assert make_etag(bytearray(b"body")) == expected
    assert make_etag(memoryview(b"body")) == expected
    assert make_etag("body") == expected
