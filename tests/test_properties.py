"""Seeded properties that tie the functions together, and a no-crash fuzz of every name."""

from __future__ import annotations

import contextlib
import random
from collections.abc import Callable
from typing import Any

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

PIECES = ['"', 'W/"', "W/", ",", ", ", " ", "\t", "a", "b", "*", "\xe9", "\x7f", "\x00"]
PIECES += ['"a"', 'W/"a"', '"b"', '""', "\n", "Ā", "\\", ",,"]
CURRENT = ['"a"', 'W/"a"', '"b"', '""', '"*"', None]


def _field(rng: random.Random) -> str:
    return "".join(rng.choice(PIECES) for _ in range(rng.randint(0, 7)))


def _parsed(field: str) -> list[EntityTag] | None:
    try:
        return parse(field)
    except ValueError:
        return None


@pytest.mark.parametrize("seed", range(4))
def test_the_evaluators_are_the_comparisons_on_valid_fields(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(3000):
        field, current = _field(rng), rng.choice(CURRENT)
        tags = _parsed(field)
        if tags is None:
            assert if_match(field, current) is False
            assert if_none_match(field, current) is True
            assert if_range(field, current) is False
            continue
        if is_wildcard(field):
            assert if_match(field, current) is (current is not None)
            assert if_none_match(field, current) is (current is None)
            continue
        if current is None:
            assert (if_match(field, None), if_none_match(field, None)) == (False, True)
            continue
        assert if_match(field, current) is matches(field, current, weak=False)
        assert if_none_match(field, current) is not matches(field, current)
        assert matches(field, current) is any(weak_compare(t, current) for t in tags)
        assert matches(field, current, weak=False) is any(strong_compare(t, current) for t in tags)
        # If-Range holds one entity-tag, not a list: '"a",' is not one.
        single = len(tags) == 1 and field.strip(" \t") == str(tags[0])
        assert if_range(field, current) is (single and strong_compare(tags[0], current))


@pytest.mark.parametrize("seed", range(2))
def test_evaluate_preconditions_follows_the_two_evaluators(seed: int) -> None:
    rng = random.Random(100 + seed)
    for _ in range(3000):
        method = rng.choice(["GET", "HEAD", "PUT", "POST", "DELETE", "get", "OPTIONS"])
        current = rng.choice(CURRENT)
        match: str | list[str] | None = rng.choice([None, [], _field(rng)])
        none_match: str | list[str] | None = rng.choice([None, [], _field(rng)])
        if method == "OPTIONS":
            expected = None
        elif match not in (None, []) and not if_match(match, current):
            expected = 412
        elif none_match not in (None, []) and not if_none_match(none_match, current):
            expected = 304 if method in ("GET", "HEAD") else 412
        else:
            expected = None
        answer = evaluate_preconditions(method, current, if_match=match, if_none_match=none_match)
        assert answer == expected


def test_tags_round_trip_through_their_header_form() -> None:
    rng = random.Random(7)
    alphabet = [chr(c) for c in [0x21, *range(0x23, 0x7F), *range(0x80, 0x100)]]
    for _ in range(3000):
        tag = EntityTag("".join(rng.choices(alphabet, k=rng.randint(0, 6))), rng.random() < 0.5)
        assert parse(str(tag)) == [tag]
        assert parse(", ".join([str(tag)] * 3)) == [tag] * 3
        assert strong_compare(tag, str(tag)) is not tag.weak
        assert weak_compare(tag, format_etag(tag.value)) is True


FUZZ: list[Callable[[Any], object]] = [
    parse,
    is_wildcard,
    lambda v: make_etag(v),
    lambda v: format_etag(v),
    lambda v: strong_compare(v, '"a"'),
    lambda v: weak_compare('"a"', v),
    lambda v: matches(v, '"a"'),
    lambda v: matches('"a"', v),
    lambda v: if_match(v, '"a"'),
    lambda v: if_none_match('"a"', v),
    lambda v: if_range(v, None),
    lambda v: evaluate_preconditions("GET", None, if_match=v),
    lambda v: evaluate_preconditions(v, None),
]


def _value(rng: random.Random) -> object:
    text = _field(rng)
    tags = [EntityTag(text, rng.random() < 0.5), EntityTag(text, 1)]  # type: ignore[arg-type]
    forms = [text, text.encode("utf-8"), bytearray(text, "utf-8"), [text, text], [text.encode()]]
    return rng.choice([*forms, *tags, None, 0, 1.5, (text,)])


@pytest.mark.parametrize("seed", range(3))
def test_every_name_raises_only_value_or_type_errors(seed: int) -> None:
    rng = random.Random(500 + seed)
    for _ in range(4000):
        value = _value(rng)
        for call in FUZZ:
            with contextlib.suppress(ValueError, TypeError):
                call(value)
