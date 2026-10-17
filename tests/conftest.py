from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

UPSTREAM = Path(__file__).resolve().parent / "upstream"


def read_upstream(name: str) -> str:
    """Return a third-party reference file as text.

    The files are not committed: `python scripts/fetch_upstream.py` fetches them. Their
    tests skip while a file is absent and fail if it differs from the manifest.
    """
    path = UPSTREAM / name
    if not path.is_file():
        pytest.skip(f"{name} is not fetched; run python scripts/fetch_upstream.py")
    entry = json.loads((UPSTREAM / "MANIFEST.json").read_text(encoding="utf-8"))[name]
    body = path.read_bytes()
    assert hashlib.sha256(body).hexdigest() == entry["sha256"], f"{name} differs from MANIFEST"
    return body.decode("utf-8")


def unpaginated(text: str) -> str:
    """Drop the page footers, headers and form feeds of an RFC so sections read as one block."""
    footer = re.compile(r"^(RFC \d{4} .*\S\s{2,}\S.*|.*\[Page \d+\])$")
    return "\n".join(
        line for line in text.splitlines() if "\f" not in line and not footer.match(line)
    )


def section(text: str, start: str, end: str) -> str:
    """The text between two headings that start a line (contents lines are indented)."""
    body = text.split("\n" + start, 1)[1]
    return body.split("\n" + end, 1)[0]


def rule(text: str, name: str) -> str:
    """The right-hand side of an ABNF rule, joined across its continuation lines."""
    match = re.search(
        rf"^ +{re.escape(name)} +=(.+?)(?=\n *\n|\n +[\w-]+ +=)", text, re.MULTILINE | re.DOTALL
    )
    assert match is not None, name
    return re.sub(r";[^\n]*", "", match.group(1))


def rfc(number: int) -> str:
    return unpaginated(read_upstream(f"rfc{number}.txt"))


@pytest.fixture(scope="session")
def rfc9110() -> str:
    """RFC 9110, see tests/upstream/MANIFEST.json for its source."""
    return rfc(9110)


@pytest.fixture(scope="session")
def rfc7232() -> str:
    """RFC 7232, see tests/upstream/MANIFEST.json for its source."""
    return rfc(7232)


@pytest.fixture(scope="session")
def rfc5234() -> str:
    """RFC 5234, see tests/upstream/MANIFEST.json for its source."""
    return rfc(5234)
