"""README, GUIDE and docstring examples run; versions and dates agree."""

from __future__ import annotations

import contextlib
import doctest
import io
import re
from pathlib import Path

import etag

ROOT = Path(__file__).resolve().parents[1]


def _python_blocks() -> list[str]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    return re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)


def _expected_prints(block: str) -> list[str]:
    # Each print line ends in a comment whose first word is the exact output.
    return re.findall(r"^print\(.*\)\s+# (\S+)", block, flags=re.MULTILINE)


def test_the_readme_has_examples() -> None:
    assert len(_python_blocks()) >= 4


def test_every_readme_example_runs_and_prints_its_comment() -> None:
    checked = 0
    for block in _python_blocks():
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(compile(block, "README.md", "exec"), {"__name__": "readme"})
        expected = _expected_prints(block)
        assert out.getvalue().splitlines() == expected
        checked += len(expected)
    assert checked >= 7


def test_the_readme_api_table_lists_every_public_name() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    table = text.split("## API", 1)[1].split("##", 1)[0]
    for name in etag.__all__:
        assert f"`{name}" in table, name


def test_version_matches_pyproject() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, flags=re.MULTILINE)
    assert match is not None
    assert match.group(1) == etag.__version__


def test_changelog_has_an_entry_for_this_version() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{etag.__version__}]" in text


def test_every_guide_example_runs() -> None:
    text = (ROOT / "GUIDE.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)
    assert len(blocks) >= 3
    for block in blocks:
        exec(compile(block, "GUIDE.md", "exec"), {"__name__": "guide"})


def test_the_guide_names_every_function_in_its_error_table() -> None:
    text = (ROOT / "GUIDE.md").read_text(encoding="utf-8")
    table = text.split("## Errors", 1)[1].split("##", 1)[0]
    for name in ("parse", "matches", "format_etag", "make_etag", "if_match"):
        assert f"`{name}" in table, name


def test_every_public_name_has_a_passing_example() -> None:
    finder = doctest.DocTestFinder(recurse=False)
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
    examples = 0
    for name in [*etag.__all__, "__module__"]:
        # Header is a type alias, which cannot hold a docstring of its own: the package
        # docstring documents it, so its examples there must name it.
        alias = name == "Header"
        target = etag if alias or name == "__module__" else getattr(etag, name)
        tests = [t for t in finder.find(target, name, globs=dict(vars(etag))) if t.examples]
        if alias:
            tests = [t for t in tests if any(name in e.source for e in t.examples)]
        assert tests, f"{name} has no example"
        for test in tests:
            examples += len(test.examples)
            assert runner.run(test).failed == 0, name
    assert examples >= 20


def test_the_changelog_dates_the_current_version() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = rf"^## \[{re.escape(etag.__version__)}\] - \d{{4}}-\d{{2}}-\d{{2}}$"
    assert re.search(heading, text, flags=re.MULTILINE)
