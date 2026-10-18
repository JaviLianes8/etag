"""Build the wheel, install it in a throwaway venv and drive the installed package.

Slow and needs the build backend, so it runs only with ETAG_E2E=1.
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("ETAG_E2E") != "1", reason="set ETAG_E2E=1 to build and install"
)

PROGRAM = """
import importlib.metadata, importlib.resources
import etag
from etag import EntityTag, evaluate_preconditions, format_etag, if_range, make_etag, parse

assert etag.__file__.find("site-packages") != -1, etag.__file__
assert etag.__version__ == "1.0.0" and EntityTag.__module__ == "etag"
assert importlib.metadata.version("etag") == etag.__version__
assert importlib.resources.files("etag").joinpath("py.typed").is_file()

current = make_etag(b"hello")
assert evaluate_preconditions("GET", current, if_none_match=[b'"x"', current]) == 304
assert evaluate_preconditions("PUT", current, if_match='W/' + current) == 412
assert evaluate_preconditions("PUT", None, if_none_match="*") is None
assert parse('"a", , W/"b"') == [("a", False), EntityTag("b", True)]
assert str(EntityTag("123-a", True)) == format_etag("123-a", weak=True) == 'W/"123-a"'
assert if_range('"123-a"', '"123-a"') and not if_range('W/"123-a"', '"123-a"')
for bad in ('"a" "b"', '*, "a"', 'w/"a"'):
    try:
        parse(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(bad)
for bad in (lambda: format_etag("a", weak=1), lambda: evaluate_preconditions(b"GET", None)):
    try:
        bad()
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError")
print("e2e ok")
"""


def _run(*cmd: str | Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, check=False
    )


def test_installed_wheel_end_to_end(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    built = _run(sys.executable, "-m", "build", "--wheel", "--outdir", dist, ROOT)
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("etag-*.whl")

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    installed = _run(python, "-m", "pip", "install", "-q", wheel)
    assert installed.returncode == 0, installed.stderr

    # Run from an empty folder so the source tree cannot shadow the install.
    work = tmp_path / "work"
    work.mkdir()
    result = _run(python, "-I", "-c", PROGRAM, cwd=work)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "e2e ok"


def test_the_archives_hold_exactly_the_package_and_its_sources(tmp_path: Path) -> None:
    import tarfile
    import zipfile

    dist = tmp_path / "dist"
    built = _run(sys.executable, "-m", "build", "--outdir", dist, ROOT)
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("etag-*.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    package = sorted(n for n in names if not n.startswith("etag-1.0.0.dist-info/"))
    modules = ["__init__", "_compare", "_conditional", "_parse", "_plain", "_tag"]
    assert package == sorted([*(f"etag/{m}.py" for m in modules), "etag/py.typed"])
    assert "etag-1.0.0.dist-info/licenses/LICENSE" in names
    (sdist,) = dist.glob("etag-*.tar.gz")
    with tarfile.open(sdist) as archive:
        members = [m.split("/", 1)[1] for m in archive.getnames() if "/" in m]
        archive.extractall(tmp_path / "sdist", filter="data")
    assert "LICENSE" in members and "GUIDE.md" in members and "PKG-INFO" in members
    assert "tests/upstream/MANIFEST.json" in members
    assert "tests/fixtures/oracle_runs.json" in members
    assert not [m for m in members if m.startswith("tests/upstream/") and m.endswith(".txt")]
    # hatchling always adds .gitignore; nothing else outside the list may slip in.
    stray = [m for m in members if "__pycache__" in m or m.startswith((".", "dist"))]
    assert stray == [".gitignore"]
    assert "CERT-1.0-REPORT.md" not in members and "IMPROVEMENTS-round.md" not in members
    # Every test module ships with the scripts the tests import, so the sdist runs its suite.
    tests = {f"tests/{path.name}" for path in (ROOT / "tests").glob("*.py")}
    assert tests <= set(members)
    scripts = {"fetch_upstream.py", "oracle_fixture.py", "oracle_runs.py"}
    assert {m for m in members if m.startswith("scripts/")} == {f"scripts/{s}" for s in scripts}
    unpacked = tmp_path / "sdist" / "etag-1.0.0"
    collected = _run(
        sys.executable, "-m", "pytest", "--co", "-q", "-p", "no:cacheprovider", cwd=unpacked
    )
    assert collected.returncode == 0, collected.stdout + collected.stderr
    assert "tests/test_references.py" in collected.stdout.replace("\\", "/")
