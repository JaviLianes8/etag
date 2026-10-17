"""Shared access to tests/fixtures/oracle_runs.json and the etag answers for its cases."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from etag import EntityTag, evaluate_preconditions, is_wildcard, parse

ROOT = Path(__file__).resolve().parents[1]
RUNS: dict[str, Any] = json.loads(
    (ROOT / "tests" / "fixtures" / "oracle_runs.json").read_text(encoding="utf-8")
)
FIELDS: list[str] = RUNS["cases"]["fields"]
SCENARIOS: list[list[str | None]] = RUNS["cases"]["scenarios"]
sys.path.insert(0, str(ROOT / "scripts"))
oracle_fixture = importlib.import_module("oracle_fixture")
oracle_runs = importlib.import_module("oracle_runs")


def ours(field: str) -> list[EntityTag] | None:
    """etag's reading of a field, or None when it rejects the field."""
    try:
        return parse(field)
    except ValueError:
        return None


def well_formed(*headers: str | None) -> bool:
    """Every header is absent or a value the grammar accepts."""
    return all(header is None or ours(header) is not None for header in headers)


def padded_wildcard(header: str | None) -> bool:
    """The wildcard with optional whitespace around it, which some readers miss."""
    return header is not None and is_wildcard(header) and header != "*"


def comma_inside(header: str | None) -> bool:
    """A well-formed list in which an opaque value holds a comma."""
    tags = ours(header) if header is not None else None
    return tags is not None and any("," in tag.value for tag in tags)


def status(scenario: list[str | None]) -> int:
    """etag's status for a scenario, with 200 for "go ahead"."""
    method, current, match, none_match = scenario
    assert method is not None
    answer = evaluate_preconditions(method, current, if_match=match, if_none_match=none_match)
    return answer or 200
