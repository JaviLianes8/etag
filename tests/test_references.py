"""etag against Werkzeug, Django and Starlette run on the same seeded inputs.

tests/fixtures/oracle_runs.json holds their answers, recorded by scripts/oracle_fixture.py
(versions in its "tools" entry). Every comparison runs on the recorded answers; when the
same versions are installed, test_live_answers_equal_the_recorded_ones reruns them. Each
known difference is named, counted and checked, never skipped.
"""

from __future__ import annotations

import importlib.metadata

import pytest
from oracle_data import (
    FIELDS,
    RUNS,
    SCENARIOS,
    comma_inside,
    oracle_fixture,
    oracle_runs,
    ours,
    padded_wildcard,
    status,
    well_formed,
)

from etag import if_none_match, is_wildcard


def test_the_cases_are_the_seeded_ones() -> None:
    assert oracle_fixture.cases() == RUNS["cases"]
    assert sum(ours(field) is None for field in FIELDS) > 500
    assert sum(ours(field) is not None for field in FIELDS) > 800


def test_werkzeug_parse_etags_reads_the_same_tags() -> None:
    padded = rejected = 0
    for field, answer in zip(FIELDS, RUNS["werkzeug"]["parse_etags"], strict=True):
        tags = ours(field)
        if tags is None:
            rejected += 1
            continue
        if padded_wildcard(field):
            # Werkzeug compares with "*" before trimming, so it reads a tag named *.
            assert answer == {"star": False, "strong": ["*"], "weak": []}, field
            padded += 1
            continue
        if is_wildcard(field):
            assert answer["star"] is True
            continue
        # Werkzeug 3.1.9 stores the empty opaque value as None.
        strong = sorted({tag.value or None for tag in tags if not tag.weak}, key=str)
        weak = sorted({tag.value or None for tag in tags if tag.weak}, key=str)
        assert answer["star"] is False
        assert sorted(answer["strong"], key=str) == strong, field
        assert sorted(answer["weak"], key=str) == weak, field
    assert padded > 20 and rejected > 500


def test_werkzeug_is_resource_modified_is_the_if_none_match_rule() -> None:
    compared = empty = 0
    for scenario, modified in zip(SCENARIOS, RUNS["werkzeug"]["is_resource_modified"], strict=True):
        if modified is None:
            continue
        _, current, _, none_match = scenario
        assert current is not None and none_match is not None
        tags = ours(none_match)
        if tags is None or padded_wildcard(none_match):
            continue
        # Werkzeug stores a listed "" as None, so the empty opaque value never matches.
        value = current.removeprefix("W/")[1:-1]
        found = any(tag.value == value and tag.value for tag in tags)
        assert modified is (not is_wildcard(none_match) and not found), scenario
        if modified is if_none_match(none_match, current):
            compared += 1
        else:
            assert value == "" and '""' in none_match
            empty += 1
    assert compared > 150 and empty > 10


def test_django_parse_etags_differs_only_by_splitting_inside_quotes() -> None:
    split = 0
    for field, answer in zip(FIELDS, RUNS["django"]["parse_etags"], strict=True):
        tags = ours(field)
        if tags is None:
            continue
        if is_wildcard(field):
            assert answer == ["*"]
        elif comma_inside(field):
            # Django splits at every comma, so a tag holding a comma is dropped.
            assert answer == [str(tag) for tag in tags if "," not in tag.value], field
            split += 1
        else:
            assert answer == [str(tag) for tag in tags], field
    assert split > 3


def test_django_get_conditional_response_agrees_on_well_formed_requests() -> None:
    compared = differs = 0
    for scenario, answer in zip(SCENARIOS, RUNS["django"]["get_conditional_response"], strict=True):
        if well_formed(*scenario[2:]) and not any(comma_inside(h) for h in scenario[2:]):
            assert status(scenario) == answer, scenario
            compared += 1
        elif status(scenario) != answer:
            # Django drops malformed members and treats a field left empty as absent.
            differs += 1
    assert compared > 2000 and differs > 50


def test_starlette_is_not_modified_agrees_on_well_formed_requests() -> None:
    compared = 0
    for scenario, not_modified in zip(SCENARIOS, RUNS["starlette"], strict=True):
        _, current, _, none_match = scenario
        if not_modified is None or not well_formed(none_match) or comma_inside(none_match):
            continue
        assert current is not None and none_match is not None
        assert not_modified is not if_none_match(none_match, current), scenario
        compared += 1
    assert compared > 150


@pytest.mark.parametrize("tool", ["werkzeug", "django", "starlette", "aiohttp"])
def test_live_answers_equal_the_recorded_ones(tool: str) -> None:
    try:
        installed = importlib.metadata.version(tool)
    except importlib.metadata.PackageNotFoundError:
        pytest.skip(f"{tool} is not installed (pip install etag[oracle])")
    if installed != RUNS["tools"][tool]:
        pytest.skip(f"{tool} {installed} installed, answers recorded with {RUNS['tools'][tool]}")
    live = getattr(oracle_runs, f"run_{tool}")(RUNS["cases"])
    assert live == RUNS[tool]
