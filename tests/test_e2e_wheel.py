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
