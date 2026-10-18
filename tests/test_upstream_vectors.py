"""Test vectors read from the fetched Werkzeug, Django and jshttp/fresh test files.

The literals are extracted from the files fetched by scripts/fetch_upstream.py when the
test runs (the tests skip when they are absent). Where those projects read malformed
input leniently, the difference is asserted, not hidden.
"""

from __future__ import annotations

import ast
import re

import pytest
from conftest import read_upstream

from etag import EntityTag, evaluate_preconditions, format_etag, if_none_match, parse


def _calls(source: str, name: str) -> list[tuple[tuple[object, ...], object]]:
    """(arguments, expected) of every ``assert name(...) == x`` or ``assertEqual(name(...), x)``.

    The test file is parsed, not executed; only calls whose arguments and expected value
    are literals are returned.
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        pair: tuple[ast.expr, ast.expr] | None = None
        if isinstance(node, ast.Compare) and len(node.comparators) == 1:
            pair = (node.left, node.comparators[0])
        elif isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "assertEqual":
            pair = (node.args[0], node.args[1])
        if pair is None or not isinstance(pair[0], ast.Call):
            continue
        func = pair[0].func
        if (getattr(func, "attr", None) or getattr(func, "id", None)) != name:
            continue
        args = tuple(ast.literal_eval(arg) for arg in pair[0].args)
        found.append((args, ast.literal_eval(pair[1])))
    return found


def test_werkzeug_quote_and_unquote_vectors() -> None:
    source = read_upstream("werkzeug-test_http.py.txt")
    quoted = _calls(source, "quote_etag")
    unquoted = _calls(source, "unquote_etag")
    assert len(quoted) == 2 and len(unquoted) == 2
    for args, expected in quoted:
        value, *weak = args
        assert format_etag(str(value), weak=bool(weak and weak[0])) == expected
    for (field,), expected in unquoted:
        assert tuple(parse(str(field))[0]) == expected


def test_werkzeug_parse_etags_vector() -> None:
    source = read_upstream("werkzeug-test_http.py.txt")
    field = re.search(r"es = http\.parse_etags\((.+)\)$", source, re.MULTILINE)
    assert field is not None
    value = ast.literal_eval(field.group(1))
    # Werkzeug keeps the unquoted member "blar"; the grammar has no such element.
    with pytest.raises(ValueError):
        parse(value)
    members = [m for m in value.split(", ") if m.startswith(('"', "W/"))]
    tags = parse(", ".join(members))
    assert {t.value for t in tags if not t.weak} == {"foo", "bar"}
    assert {t.value for t in tags if t.weak} == {"baz"}
    assert "blar" in value and "blar" not in {t.value for t in tags}


def test_django_parse_etags_vectors() -> None:
    source = read_upstream("django-test_http.py.txt")
    vectors = _calls(source, "parse_etags")
    assert len(vectors) == 3
    accepted, star, lenient = vectors
    assert [str(tag) for tag in parse(str(accepted[0][0]))] == accepted[1]
    assert parse(str(star[0][0])) == [EntityTag("*")] and star[1] == ["*"]
    # Django drops the member with escaped quotes and keeps the rest; etag rejects the field.
    with pytest.raises(ValueError):
        parse(str(lenient[0][0]))
    assert lenient[1] == ['"etag"']


def _constants(source: str) -> dict[str, str]:
    pairs = re.findall(r'^(\w*ETAG) = (".*"|\'.*\')', source, flags=re.MULTILINE)
    return {name: ast.literal_eval(value) for name, value in pairs}


# Scenarios of Django's tests/conditional_processing/tests.py, transcribed by hand from
# the named tests: (test, method, current tag, If-Match, If-None-Match, status).
DJANGO_SCENARIOS = [
    ("test_if_none_match", "GET", "ETAG", None, "ETAG", 304),
    ("test_if_none_match", "PUT", "ETAG", None, "ETAG", 412),
    ("test_if_none_match", "GET", "ETAG", None, "EXPIRED_ETAG", 200),
    ("test_weak_if_none_match", "GET", "WEAK_ETAG", None, "ETAG", 304),
    ("test_weak_if_none_match", "PUT", "WEAK_ETAG", None, "WEAK_ETAG", 412),
    ("test_weak_if_none_match", "GET", "ETAG", None, "WEAK_ETAG", 304),
    ("test_all_if_none_match", "GET", "ETAG", None, "*", 304),
    ("test_all_if_none_match", "PUT", "ETAG", None, "*", 412),
    ("test_all_if_none_match", "GET", None, None, "*", 200),
    ("test_if_match", "PUT", "ETAG", "ETAG", None, 200),
    ("test_if_match", "PUT", "ETAG", "EXPIRED_ETAG", None, 412),
    ("test_weak_if_match", "GET", "WEAK_ETAG", "ETAG", None, 412),
    ("test_weak_if_match", "GET", "WEAK_ETAG", "WEAK_ETAG", None, 412),
    ("test_weak_if_match", "GET", "ETAG", "WEAK_ETAG", None, 412),
    ("test_all_if_match", "GET", "ETAG", "*", None, 200),
    ("test_all_if_match", "GET", None, "*", None, 412),
]


@pytest.mark.parametrize(
    ("test", "method", "current", "match", "none_match", "code"), DJANGO_SCENARIOS
)
def test_django_conditional_processing_scenarios(
    test: str,
    method: str,
    current: str | None,
    match: str | None,
    none_match: str | None,
    code: int,
) -> None:
    source = read_upstream("django-conditional_tests.py.txt")
    assert f"def {test}(self)" in source
    tags = {**_constants(source), "*": "*"}
    assert len(tags) == 4

    def tag(name: str | None) -> str | None:
        return None if name is None else tags[name]

    answer = evaluate_preconditions(
        method, tag(current), if_match=tag(match), if_none_match=tag(none_match)
    )
    assert (answer or 200) == code


def _js_object(text: str) -> dict[str, str]:
    """A JavaScript object literal of string values, as the fresh tests write them."""
    pairs = re.findall(r"(?:'([^']*)'|([\w-]+)): '([^']*)'", text)
    return {quoted or bare: value for quoted, bare, value in pairs}


def test_fresh_if_none_match_vectors() -> None:
    source = read_upstream("fresh-test.js.txt")
    cases = re.findall(
        r"var reqHeaders = (\{.*\})\n\s+var resHeaders = (\{.*\})\n\s+assert\.ok\((!?)fresh",
        source,
    )
    assert len(cases) == 23
    checked = 0
    for request, response, negated in cases:
        headers, served = _js_object(request), _js_object(response)
        if "if-none-match" not in headers or "cache-control" in headers:
            continue  # dates and Cache-Control are outside etag
        # Section 13.2.2: If-Modified-Since is not evaluated when If-None-Match is present.
        not_modified = not if_none_match(headers["if-none-match"], served.get("etag"))
        assert not_modified is (negated == ""), (headers, served)
        checked += 1
    assert checked == 14
