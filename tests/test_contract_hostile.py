"""Hostile arguments: subclasses cannot steer results, messages stay short, time stays linear."""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest

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


class LyingText(str):
    """Text whose methods lie about its content."""

    def strip(self, chars: str | None = None) -> str:
        return "*"

    def startswith(self, *args: object) -> bool:
        return True

    def find(self, *args: object) -> int:
        return -1

    def __eq__(self, other: object) -> bool:
        return True

    def __hash__(self) -> int:
        return 0

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter("")

    def __str__(self) -> str:
        return '"forged"'

    def encode(self, *args: object) -> bytes:
        return b"forged"


class LyingBytes(bytes):
    def decode(self, *args: object) -> str:
        return "*"


class LyingTag(EntityTag):
    @property
    def value(self) -> str:
        return "forged"


def test_text_subclasses_are_read_as_their_characters() -> None:
    assert parse(LyingText('"a"')) == [EntityTag("a")]
    assert parse([LyingText('"a"'), LyingText("")]) == [EntityTag("a")]
    assert is_wildcard(LyingText('"a"')) is False
    assert format_etag(LyingText("a")) == '"a"'
    with pytest.raises(ValueError):
        format_etag(LyingText("a b"))
    assert make_etag(LyingText("abc")) == make_etag(b"abc")
    assert strong_compare(LyingText('"a"'), '"b"') is False
    assert weak_compare('"a"', EntityTag(LyingText("b"))) is False
    assert matches('"x"', LyingText('"a"')) is False


class LyingIndex(str):
    def __getitem__(self, key: object) -> str:
        return "Z"


def test_a_surrogate_is_named_from_the_text_itself() -> None:
    with pytest.raises(ValueError, match=r"^U\+D800 cannot be encoded as UTF-8 at 1$"):
        make_etag(LyingIndex("a\ud800"))


class IteratingTag(EntityTag):
    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(['"a"'])


def test_entity_tags_are_never_headers_and_always_have_two_fields() -> None:
    for header in (IteratingTag("x"), EntityTag("x")):
        with pytest.raises(TypeError):
            parse(header)  # type: ignore[arg-type]
    for fields in ((), ("a",), ("a", False, "zz")):
        bad = tuple.__new__(EntityTag, fields)
        with pytest.raises(TypeError, match="two fields"):
            strong_compare(bad, '"a"')


def test_bytes_subclasses_are_read_as_their_octets() -> None:
    assert parse(LyingBytes(b'"a"')) == [EntityTag("a")]
    assert is_wildcard([LyingBytes(b'"a"')]) is False


def test_entity_tag_subclasses_are_read_as_their_fields() -> None:
    assert strong_compare(LyingTag("a"), '"a"') is True
    assert strong_compare(LyingTag("a"), '"forged"') is False
    assert if_match('"a"', LyingTag("a")) is True


def test_a_method_subclass_cannot_pretend_to_be_get() -> None:
    method = LyingText("PUT")
    assert evaluate_preconditions(method, '"a"', if_none_match='"a"') == 412
    assert evaluate_preconditions(LyingText("OPTIONS"), '"a"', if_match='"b"') is None


class Meta(type):
    @property
    def __name__(cls) -> str:  # type: ignore[override]
        return "x" * 100_000


def test_type_names_in_messages_are_bounded() -> None:
    long_name = type("L" * 100_000, (), {})()
    tricky = Meta("Tricky", (), {})()
    for value in (long_name, tricky):
        for call in (parse, lambda v: format_etag(v), lambda v: make_etag(v)):
            with pytest.raises(TypeError) as caught:
                call(value)
            assert len(str(caught.value)) < 120
        with pytest.raises(TypeError) as caught:
            format_etag("a", weak=value)
        assert len(str(caught.value)) < 120
    # The name slot of the class is reported, not what a metaclass property claims.
    with pytest.raises(TypeError, match=r"not Tricky$"):
        parse(tricky)


HUGE = 'W/"' + "a" * 1_000_000
ERRORS: list[Callable[[], object]] = [
    lambda: parse(HUGE),
    lambda: parse('"a"' + " x" * 500_000),
    lambda: parse('"' + "\x00" * 1_000_000 + '"'),
    lambda: format_etag("a" * 1_000_000 + " "),
    lambda: strong_compare(HUGE, '"a"'),
    lambda: matches('"a"', '"a", ' * 200_000),
]


@pytest.mark.parametrize("call", ERRORS)
def test_value_error_messages_never_echo_the_input(call: Callable[[], object]) -> None:
    with pytest.raises(ValueError) as caught:
        call()
    message = str(caught.value)
    assert len(message) < 80 and "aaaa" not in message and "\x00" not in message


def _seconds(call: Callable[[], object]) -> float:
    best = float("inf")
    for _ in range(3):
        start = time.perf_counter()
        call()
        best = min(best, time.perf_counter() - start)
    return best


PATTERNS: list[Callable[[int], str]] = [
    lambda n: '"a", ' * n,
    lambda n: ", " * n + '"a"',
    lambda n: 'W/"' + "\xe9" * (5 * n) + '"',
    lambda n: " \t" * n + '"a"' + " \t" * n,
]


@pytest.mark.parametrize("pattern", PATTERNS)
def test_time_grows_linearly(pattern: Callable[[int], str]) -> None:
    small, large = pattern(20_000), pattern(200_000)

    def evaluate(field: str) -> Callable[[], object]:
        return lambda: (if_none_match(field, '"b"'), if_match(field, '"a"'), if_range(field, None))

    ratio = _seconds(evaluate(large)) / max(_seconds(evaluate(small)), 1e-6)
    assert ratio < 30, ratio
