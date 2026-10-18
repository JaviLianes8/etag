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
print(json.dumps({"version": etag.__version__, "results": results, "changed": changed()}))
"""

# One probe per change listed in CHANGELOG 1.0.0, run before the results above are printed.
CHANGED = r"""
class Lying(str):
    def strip(self, chars=None):
        return "*"

class Buffered(bytearray):
    def __buffer__(self, flags):
        return memoryview(b'"forged"')

    def __release_buffer__(self, view):
        pass

class Claims:
    __class__ = property(lambda self: bool)

    def __bool__(self):
        return True

class Short(list):
    def __len__(self):
        return 0

def text(call):
    try:
        call()
    except (TypeError, ValueError) as error:
        return str(error)

def changed():
    evaluate, Tag = etag.evaluate_preconditions, etag.EntityTag
    return {
        "weak_int": outcome(lambda: etag.format_etag("a", weak=1)),
        "weak_claim": outcome(lambda: etag.format_etag("a", weak=Claims())),
        "method_bytes": outcome(lambda: evaluate(b"GET", '"a"', if_none_match='"a"')),
        "header_zero": outcome(lambda: evaluate("GET", '"a"', if_match=0)),
        "ignored_method_header": outcome(lambda: evaluate("OPTIONS", None, if_none_match=0)),
        "unread_if_none_match": outcome(
            lambda: evaluate("PUT", '"a"', if_match='"b"', if_none_match=0)),
        "matches_weak_target": outcome(lambda: etag.matches('"a" "b"', 'W/"a"', weak=False)),
        "make_etag_surrogate": outcome(lambda: etag.make_etag("\ud800")),
        "text_subclass": outcome(lambda: etag.is_wildcard(Lying('"a"'))),
        "buffer_subclass": outcome(lambda: etag.parse(Buffered(b'"a"'))),
        "length_zero_list": outcome(lambda: evaluate("PUT", '"a"', if_match=Short(['"b"']))),
        "entity_tag_lines": outcome(lambda: etag.parse(tuple.__new__(Tag, ('"x"',)))),
        "three_fields": outcome(
            lambda: etag.strong_compare(tuple.__new__(Tag, ("a", False, 1)), '"a"')),
        "module": Tag.__module__,
        "annotations": hasattr(etag, "annotations"),
        "messages": [text(lambda: etag.parse('  "a" x')), text(lambda: etag.parse('  W/"ab')),
                     text(lambda: etag.strong_compare(' "a" "b"', '"a"')),
                     text(lambda: etag.format_etag("ab c"))],
        "make_etag_type": text(lambda: etag.make_etag(1)),
        "type_name_length": len(text(lambda: etag.parse(type("L" * 100, (), {})()))),
    }
"""
PROBE = PROBE.replace("print(json.dumps(", CHANGED + "\nprint(json.dumps(")


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
    buffered = "forged" if sys.version_info >= (3, 12) else "a"  # __buffer__ is 3.12+
    assert old["changed"].pop("make_etag_type")  # CPython's own message, varying by version
    assert old["changed"] == {
        "weak_int": ["ok", "'W/\"a\"'"],
        "weak_claim": ["ok", "'W/\"a\"'"],
        "method_bytes": ["ok", "412"],
        "header_zero": ["ok", "None"],
        "ignored_method_header": ["ok", "None"],
        "unread_if_none_match": ["ok", "412"],
        "matches_weak_target": ["ok", "False"],
        "make_etag_surrogate": ["UnicodeEncodeError"],
        "text_subclass": ["ok", "True"],
        "buffer_subclass": ["ok", f"[EntityTag(value='{buffered}', weak=False)]"],
        "length_zero_list": ["ok", "None"],
        "entity_tag_lines": ["ok", "[EntityTag(value='x', weak=False)]"],
        "three_fields": ["ok", "True"],
        "module": "etag._tag",
        "annotations": True,
        "messages": [
            "expected a comma at position 4",
            "unterminated opaque-tag",
            "expected a single entity-tag",
            "invalid character ' ' in opaque-tag at position 2",
        ],
        "type_name_length": 149,
    }
    type_error, value_error = ["TypeError"], ["ValueError"]
    assert new["changed"] == {
        **dict.fromkeys(["weak_int", "weak_claim", "method_bytes", "header_zero"], type_error),
        **dict.fromkeys(["ignored_method_header", "unread_if_none_match"], type_error),
        **dict.fromkeys(["entity_tag_lines", "three_fields"], type_error),
        **dict.fromkeys(["matches_weak_target", "make_etag_surrogate"], value_error),
        "text_subclass": ["ok", "False"],
        "buffer_subclass": ["ok", "[EntityTag(value='a', weak=False)]"],
        "length_zero_list": ["ok", "412"],
        "module": "etag",
        "annotations": False,
        "messages": [
            "expected a comma at position 6",
            "unterminated opaque-tag at position 4",
            "expected a single entity-tag, more at position 4",
            "U+0020 is not allowed in an opaque-tag at 2",
        ],
        "make_etag_type": "data must be bytes-like or str, not int",
        "type_name_length": 89,
    }
