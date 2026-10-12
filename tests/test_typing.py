"""The public API is typed: mypy infers the documented types and rejects wrong ones."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

api = pytest.importorskip("mypy.api")

SRC = Path(__file__).resolve().parents[1] / "src"

SNIPPET = """
from etag import EntityTag, evaluate_preconditions, if_match, parse, strong_compare

reveal_type(parse('"a"'))
reveal_type(parse('"a"')[0].value)
reveal_type(evaluate_preconditions("GET", '"a"', if_none_match=[b'"a"']))
reveal_type(if_match("*", EntityTag("a")))
strong_compare('"a"', 3)
parse(3)
"""


@pytest.fixture(scope="module")
def mypy_output(tmp_path_factory: pytest.TempPathFactory) -> str:
    folder = tmp_path_factory.mktemp("typing")
    target = folder / "snippet.py"
    target.write_text(SNIPPET, encoding="utf-8")
    config = folder / "mypy.ini"
    config.write_text(f"[mypy]\nmypy_path = {SRC.as_posix()}\n", encoding="utf-8")
    cache = str(folder / "cache")
    out, err, _ = api.run(
        ["--strict", "--config-file", str(config), "--cache-dir", cache, str(target)]
    )
    return str(out) + str(err)


def test_parse_returns_a_list_of_entity_tags(mypy_output: str) -> None:
    assert _revealed(mypy_output, 4) == "list[tuple[str, bool, fallback=etag._tag.EntityTag]]"


def test_entity_tag_fields_are_typed(mypy_output: str) -> None:
    assert _revealed(mypy_output, 5) == "str"


def test_evaluate_preconditions_returns_a_status_literal(mypy_output: str) -> None:
    revealed = _revealed(mypy_output, 6).replace("Literal[304] | Literal[412]", "Literal[304, 412]")
    assert revealed == "Literal[304, 412] | None"


def test_evaluators_return_bool(mypy_output: str) -> None:
    assert _revealed(mypy_output, 7) == "bool"


def test_wrong_argument_types_are_rejected(mypy_output: str) -> None:
    assert re.search(r"snippet\.py:8: error: .*\[arg-type\]", mypy_output)
    assert re.search(r"snippet\.py:9: error: .*\[arg-type\]", mypy_output)


def _revealed(output: str, line: int) -> str:
    match = re.search(rf"snippet\.py:{line}: note: Revealed type is \"(.+)\"", output)
    assert match, output
    # Older mypy releases spell builtins with their module prefix.
    return match.group(1).replace("builtins.", "")
