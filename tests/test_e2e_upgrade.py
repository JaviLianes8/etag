"""Install etag 0.2.0 from PyPI, probe it, upgrade in place to this wheel, probe again.

Needs the network and the build backend, so it runs only with ETAG_E2E_PYPI=1. Every
result on well-typed input must be identical; the changes listed in the 1.0.0 section of
CHANGELOG.md are probed separately and must differ exactly as listed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("ETAG_E2E_PYPI") != "1", reason="set ETAG_E2E_PYPI=1 to run"
)

PROBE = r"""
import json, pickle, random
import etag

def outcome(call):
    try:
        result = call()
    except (TypeError, ValueError) as error:
        return [type(error).__name__]
    return ["ok", repr(result)]

rng = random.Random(1)
pieces = ['"', 'W/"', "W/", ",", ", ", " ", "\t", "a", "b", "*", "\xe9", "\x7f", '"a"', 'W/"a"']
pieces += ['""', '"*"', "Ā", ",,"]
fields = ["".join(rng.choice(pieces) for _ in range(rng.randrange(8))) for _ in range(700)]
tags = ['"a"', 'W/"a"', '"b"', '""', '"*"']
results = []
for field in fields:
    forms = [field, field.encode("utf-8"), [field, '"x"']]
    for header in forms:
        results.append(outcome(lambda: etag.parse(header)))
        results.append(outcome(lambda: etag.is_wildcard(header)))
        for tag in tags + [None]:
            results.append(outcome(lambda: etag.if_match(header, tag)))
            results.append(outcome(lambda: etag.if_none_match(header, tag)))
            results.append(outcome(lambda: etag.if_range(header, tag)))
            for method in ("GET", "PUT", "OPTIONS"):
                results.append(outcome(lambda: etag.evaluate_preconditions(
                    method, tag, if_match=header if rng.random() < 0.5 else None,
                    if_none_match=header)))
        for tag in tags[:2]:
            results.append(outcome(lambda: etag.matches(header, tag)))
            results.append(outcome(lambda: etag.matches(header, '"a"', weak=False)))
    results.append(outcome(lambda: etag.strong_compare(field, '"a"')))
    results.append(outcome(lambda: etag.weak_compare('W/"a"', field)))
    results.append(outcome(lambda: etag.make_etag(field)))
    results.append(outcome(lambda: etag.format_etag(field, weak=True)))
changed = {
    "weak_int": outcome(lambda: etag.format_etag("a", weak=1)),
    "method_bytes": outcome(
        lambda: etag.evaluate_preconditions(b"GET", '"a"', if_none_match='"a"')),
    "header_zero": outcome(lambda: etag.evaluate_preconditions("GET", '"a"', if_match=0)),
    "matches_weak_target": outcome(lambda: etag.matches('"a" "b"', 'W/"a"', weak=False)),
    "module": etag.EntityTag.__module__,
    "annotations": hasattr(etag, "annotations"),
}
print(json.dumps({"version": etag.__version__, "results": results, "changed": changed}))
"""


def _run(*cmd: str | Path, cwd: Path | None = None) -> str:
    done = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def test_upgrade_from_pypi_0_2_0_keeps_every_result(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _run(sys.executable, "-m", "build", "--wheel", "--outdir", dist, ROOT)
    (wheel,) = dist.glob("etag-1.0.0-*.whl")
    venv.create(tmp_path / "venv", with_pip=True)
    bindir = tmp_path / "venv" / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    work = tmp_path / "work"
    work.mkdir()
    _run(python, "-m", "pip", "install", "-q", "--no-cache-dir", "etag==0.2.0")
    old = json.loads(_run(python, "-I", "-c", PROBE, cwd=work))
    _run(python, "-m", "pip", "install", "-q", "--no-cache-dir", "--upgrade", wheel)
    new = json.loads(_run(python, "-I", "-c", PROBE, cwd=work))

    assert (old["version"], new["version"]) == ("0.2.0", "1.0.0")
    assert len(new["results"]) > 50_000
    assert new["results"] == old["results"]
    assert old["changed"] == {
        "weak_int": ["ok", "'W/\"a\"'"],
        "method_bytes": ["ok", "412"],
        "header_zero": ["ok", "None"],
        "matches_weak_target": ["ok", "False"],
        "module": "etag._tag",
        "annotations": True,
    }
    assert new["changed"] == {
        "weak_int": ["TypeError"],
        "method_bytes": ["TypeError"],
        "header_zero": ["TypeError"],
        "matches_weak_target": ["ValueError"],
        "module": "etag",
        "annotations": False,
    }
