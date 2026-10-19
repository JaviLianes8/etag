"""Record what established HTTP implementations answer for seeded entity-tag inputs.

Runs Werkzeug, Django, aiohttp and Starlette (pip install etag[oracle]) and, when node and
the fetched copy of jshttp/fresh are present, Node with fresh, on the same seeded inputs.
Their answers go to tests/fixtures/oracle_runs.json, which tests/test_references.py
compares with etag. That file is program output of those tools, not a copy of them.

    python scripts/fetch_upstream.py
    python scripts/oracle_fixture.py
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import random
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from oracle_runs import run_aiohttp, run_django, run_starlette, run_werkzeug

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "oracle_runs.json"
FRESH = ROOT / "tests" / "upstream" / "fresh-index.js.txt"
SEED = 9110
PIECES = ['"', 'W/"', "W/", "w/", ",", ", ", " ", "\t", "a", "b", "*", "\\", "\x7f", "\xe9"]
PIECES += ['"a"', 'W/"a"', '"b"', 'W/"b"', '""', '"a,b"', '"*"', "\x00", "\n"]
TAGS = ['"a"', 'W/"a"', '"b"', 'W/"b"', '"c"', '""', '"*"', '"\xe9"', 'W/""']
CURRENT = ['"a"', 'W/"a"', '"b"', '""', '"*"', None]
METHODS = ["GET", "HEAD", "PUT", "POST", "DELETE"]
NODE = """
const fresh = require(process.argv[1]);
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(cases.map(([field, etag]) =>
  fresh({'if-none-match': field}, {etag: etag}))));
"""


def _well_formed(rng: random.Random) -> str:
    """A well-formed list, the wildcard, or one field with a single random piece changed."""
    if rng.random() < 0.08:
        return rng.choice(["*", " * ", "\t*"])
    tags = [rng.choice(TAGS) for _ in range(rng.randint(1, 4))]
    field = "".join(t + rng.choice([",", ", ", " ,\t", ",,", " , , "]) for t in tags[:-1])
    field = rng.choice(["", " ", ", "]) + field + tags[-1] + rng.choice(["", " ", ","])
    if rng.random() < 0.3:
        at = rng.randrange(len(field) + 1)
        field = field[:at] + rng.choice(PIECES) + field[at + 1 :]
    return field


def cases() -> dict[str, Any]:
    """The seeded inputs; the same seed always gives the same cases."""
    rng = random.Random(SEED)
    fields = ["".join(rng.choice(PIECES) for _ in range(rng.randint(0, 8))) for _ in range(800)]
    fields += [_well_formed(rng) for _ in range(1200)]
    scenarios = []
    for _ in range(3000):
        match = _well_formed(rng) if rng.random() < 0.4 else None
        none_match = _well_formed(rng) if rng.random() < 0.7 else None
        scenarios.append([rng.choice(METHODS), rng.choice(CURRENT), match, none_match])
    return {"fields": fields, "scenarios": scenarios}


def node_fresh(pairs: list[list[str]]) -> list[bool] | None:
    """jshttp/fresh on If-None-Match and the response ETag, or None without node or fresh."""
    node = shutil.which("node")
    if node is None or not FRESH.is_file():
        return None
    module = FRESH.parent / "fresh-index.js"
    module.write_bytes(FRESH.read_bytes())  # Node resolves modules by their .js name.
    try:
        done = subprocess.run(
            [node, "-e", NODE, str(module)],
            input=json.dumps(pairs),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    finally:
        module.unlink()
    answers: list[bool] = json.loads(done.stdout)
    return answers


def fresh_pairs(case: dict[str, Any]) -> list[list[str]]:
    """(If-None-Match, current ETag) for every GET scenario that has both."""
    return [[s[3], s[1]] for s in case["scenarios"] if s[0] == "GET" and s[1] and s[3]]


def tools() -> dict[str, str | None]:
    node = shutil.which("node")
    version = None
    if node is not None:
        version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    names = ("werkzeug", "django", "aiohttp", "starlette")
    found: dict[str, str | None] = {name: importlib.metadata.version(name) for name in names}
    return {"python": platform.python_version(), **found, "node": version and version.strip()}


def main() -> int:
    case = cases()
    record: dict[str, Any] = {
        "tools": tools(),
        "seed": SEED,
        "cases": case,
        "werkzeug": run_werkzeug(case),
        "django": run_django(case),
        "aiohttp": run_aiohttp(case),
        "starlette": run_starlette(case),
        "fresh": node_fresh(fresh_pairs(case)),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(record, ensure_ascii=True, indent=0) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT}: {len(case['fields'])} fields, {len(case['scenarios'])} scenarios")
    return 0


if __name__ == "__main__":
    sys.exit(main())
