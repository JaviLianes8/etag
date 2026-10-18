"""Random field values checked against a regular expression of the RFC 9110 grammar.

The expression is derived by hand from the ABNF in sections 5.5, 5.6.1.2, 5.6.3, 8.8.3
and 13.1 (https://www.rfc-editor.org/rfc/rfc9110.txt); it is not copied from the RFC.
"""

from __future__ import annotations

import random
import re

import pytest

from etag import EntityTag, is_wildcard, parse

ETAGC = r"[\x21\x23-\x7e\x80-\xff]"
ENTITY_TAG = rf'(W/)?"({ETAGC}*)"'
OWS = r"[ \t]*"
# Recipient list form: [ element ] *( OWS "," OWS [ element ] ), at least one element.
LIST = rf"(?:{ENTITY_TAG})?(?:{OWS},{OWS}(?:{ENTITY_TAG})?)*"
# The wildcard, with only empty elements around it, which recipients skip (5.6.1.2).
STAR = rf"(?:,{OWS})*\*(?:{OWS},)*"
WILD = re.compile(rf"{OWS}{STAR}{OWS}")
FIELD = re.compile(rf"{OWS}(?:{STAR}|{LIST}){OWS}")
TAG = re.compile(ENTITY_TAG)

PIECES = ['"', '"', 'W/"', "W/", "w/", ",", ", ", " ", "\t", "a", "b", "*", "\\", "\x7f"]
PIECES += ["\x80", "\xff", "Ā", "\n", "\xa0", "\x00", '"x"', 'W/"y"', '""']


def oracle(field: str) -> list[EntityTag] | None:
    """The tags the grammar reads from ``field``, or ``None`` when it is invalid."""
    if FIELD.fullmatch(field) is None:
        return None
    if WILD.fullmatch(field):
        return [EntityTag("*")]
    tags = [EntityTag(m.group(2), m.group(1) is not None) for m in TAG.finditer(field)]
    return tags or None


def _random_field(rng: random.Random) -> str:
    return "".join(rng.choice(PIECES) for _ in range(rng.randint(0, 9)))


def _mutated_valid_field(rng: random.Random) -> str:
    tags = [str(EntityTag(rng.choice(["", "a", "1-2", "\xe9"]), rng.random() < 0.5))]
    tags += [str(EntityTag("b", rng.random() < 0.5)) for _ in range(rng.randint(0, 3))]
    field = rng.choice([",", ", ", " ,\t", ",,"]).join(tags)
    if rng.random() < 0.5:
        at = rng.randint(0, len(field))
        field = field[:at] + rng.choice(PIECES) + field[at + 1 :]
    return field


def _check(field: str) -> None:
    expected = oracle(field)
    try:
        got: list[EntityTag] | None = parse(field)
    except ValueError:
        got = None
    assert got == expected, repr(field)
    assert is_wildcard(field) is (WILD.fullmatch(field) is not None)


@pytest.mark.parametrize("seed", range(4))
def test_random_fields_agree_with_the_grammar(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(2500):
        _check(_random_field(rng))


@pytest.mark.parametrize("seed", range(4))
def test_mutated_valid_lists_agree_with_the_grammar(seed: int) -> None:
    rng = random.Random(1000 + seed)
    for _ in range(2500):
        _check(_mutated_valid_field(rng))


def test_the_generators_reach_both_outcomes() -> None:
    rng = random.Random(7)
    fields = [_random_field(rng) for _ in range(500)]
    fields += [_mutated_valid_field(rng) for _ in range(500)]
    outcomes = [oracle(field) is None for field in fields]
    assert 100 < sum(outcomes) < 900
