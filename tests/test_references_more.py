"""etag against aiohttp, jshttp/fresh (Node) and the documented nginx order.

aiohttp and fresh answers come from tests/fixtures/oracle_runs.json (recorded by
scripts/oracle_fixture.py); fresh is rerun live when node and the fetched copy of its
index.js are present, and the fetched Express source shows that `req.fresh` is fresh.
nginx cannot run here, so its fetched source is read for the order and the comparison
it applies.
"""

from __future__ import annotations

import json
import re
import shutil

import pytest
from conftest import read_upstream
from oracle_data import (
    FIELDS,
    RUNS,
    SCENARIOS,
    comma_inside,
    oracle_fixture,
    ours,
    padded_wildcard,
    status,
    well_formed,
)

from etag import if_none_match, is_wildcard


def canonical(header: str | None) -> bool:
    """Well-formed, no whitespace around the value, no empty element, no empty tag."""
    if header is None:
        return True
    tags = ours(header)
    if tags is None or header != header.strip(" \t"):
        return False
    empty_element = re.search(r"(^|,)[ \t]*,", header) is not None
    return not empty_element and all(tag.value for tag in tags)


def test_aiohttp_reads_a_prefix_of_the_same_tags() -> None:
    equal = cut = 0
    for field, answer in zip(FIELDS, RUNS["aiohttp"]["parse"], strict=True):
        tags = ours(field)
        if tags is None or is_wildcard(field):
            continue
        assert answer is not None
        # aiohttp stops at leading whitespace, an empty element or an empty tag.
        assert answer == [[tag.weak, tag.value] for tag in tags[: len(answer)]], field
        if canonical(field):
            assert len(answer) == len(tags), field
            equal += 1
        elif len(answer) < len(tags):
            cut += 1
    assert equal > 50 and cut > 300


def _star_tag(header: str | None) -> bool:
    # aiohttp takes a list holding only the tag "*" for the wildcard.
    return header is not None and not is_wildcard(header) and ours(header) == [("*", False)]


def test_aiohttp_file_response_agrees_on_canonical_requests() -> None:
    compared = differs = stars = 0
    for scenario, answer in zip(SCENARIOS, RUNS["aiohttp"]["file_response"], strict=True):
        if answer is None:
            continue
        headers = scenario[2:]
        if any(_star_tag(h) for h in headers):
            stars += 1
        elif all(canonical(h) or h == "*" for h in headers):
            assert status(scenario) == answer, scenario
            compared += 1
        elif status(scenario) != answer:
            assert not all(canonical(h) for h in headers)
            differs += 1
    assert compared > 150 and differs > 50 and stars > 3


def _fresh_comparable(none_match: str) -> bool:
    # fresh splits at every comma, trims only spaces and takes "*" only unpadded.
    return (
        well_formed(none_match)
        and "\t" not in none_match
        and not padded_wildcard(none_match)
        and not comma_inside(none_match)
    )


def test_fresh_agrees_where_its_tokenizer_can_read_the_field() -> None:
    answers = RUNS["fresh"]
    if answers is None:
        pytest.skip("the fixture was recorded without node")
    pairs = oracle_fixture.fresh_pairs(RUNS["cases"])
    compared = differs = tabs = 0
    for (none_match, current), is_fresh in zip(pairs, answers, strict=True):
        if _fresh_comparable(none_match):
            assert is_fresh is not if_none_match(none_match, current), (none_match, current)
            compared += 1
        elif is_fresh is if_none_match(none_match, current):
            differs += 1
            # Spaces are trimmed (those fields are compared above); tabs are not.
            tabs += _fresh_comparable(none_match.replace("\t", " "))
    assert compared > 150 and differs > 10 and tabs > 0


def test_express_5_answers_req_fresh_with_fresh_2() -> None:
    package = json.loads(read_upstream("express-package.json.txt"))
    assert package["version"] == "5.3.0" and package["dependencies"]["fresh"] == "^2.0.0"
    request = read_upstream("express-request.js.txt")
    assert "var fresh = require('fresh');" in request
    getter = request.split("defineGetter(req, 'fresh', function(){", 1)[1].split("\n});")[0]
    assert "return fresh(this.headers, {" in getter


def test_fresh_live_equals_the_recorded_answers() -> None:
    read_upstream("fresh-index.js.txt")
    if shutil.which("node") is None or RUNS["fresh"] is None:
        pytest.skip("node is not installed")
    live = oracle_fixture.node_fresh(oracle_fixture.fresh_pairs(RUNS["cases"]))
    assert live == RUNS["fresh"]


def test_nginx_evaluates_if_match_strongly_before_if_none_match_weakly() -> None:
    source = read_upstream("nginx-not_modified.c.txt")
    body = source.split("ngx_http_not_modified_header_filter(ngx_http_request_t *r)\n{", 1)[1]
    strong = body.index("ngx_http_test_if_match(r, r->headers_in.if_match, 0)")
    weak = body.index("ngx_http_test_if_match(r, r->headers_in.if_none_match, 1)")
    assert strong < weak
    assert "NGX_HTTP_PRECONDITION_FAILED" in body[:weak]
    assert "NGX_HTTP_NOT_MODIFIED" in body[weak:]
    head = "ngx_http_test_if_match(ngx_http_request_t *r, ngx_table_elt_t *header,"
    test = source.split(head, 1)[1]
    # W/ is skipped only under "weak"; otherwise the bytes are compared as they are.
    assert test.count("if (weak") == 2 and "ngx_strncmp(start, etag.data, etag.len)" in test
    assert "list->len == 1 && list->data[0] == '*'" in test


def test_aiohttp_reads_whitespace_its_own_way() -> None:
    request = pytest.importorskip("aiohttp.web_request").BaseRequest

    def values(field: str) -> list[str]:
        return [tag.value for tag in request._if_match_or_none_impl(field)]

    assert values('"a" ') == [] and ours('"a" ') == [("a", False)]
    for field in ('"a"\x0b,\x0b"b"', '"a"\r\n,"b"'):
        assert values(field) == ["a", "b"] and ours(field) is None
