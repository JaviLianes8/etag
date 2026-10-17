"""RFC 7232, which RFC 9110 obsoletes, defines the same entity-tags and the same order.

Both RFCs are read from the files fetched by scripts/fetch_upstream.py (the tests skip
when they are absent), so a 0.1 user who followed RFC 7232 gets the same answers.
"""

from __future__ import annotations

import re

from conftest import rule, section
from test_rfc9110 import _field_lines, _steps, _table_3, code_points

from etag import parse, strong_compare, weak_compare


def test_etagc_is_the_same_set(rfc7232: str, rfc9110: str) -> None:
    # RFC 7232 refers to RFC 7230 for obs-text, which RFC 9110 defines as %x80-FF.
    body = re.sub(r"\s+", " ", rule(rfc7232, "etagc")).strip()
    assert body == "%x21 / %x23-7E / obs-text"
    old = {0x21, *range(0x23, 0x7F)} | code_points(rfc9110, "obs-text")
    assert old == code_points(rfc9110, "etagc")
    # %x57.2F is the octet sequence W then /, so case-sensitive like %s"W/".
    assert rule(rfc7232, "weak").split() == ["%x57.2F"]
    assert rule(rfc9110, "weak").strip() == '%s"W/"'


def test_the_comparison_table_did_not_change(rfc7232: str, rfc9110: str) -> None:
    old = section(rfc7232, "2.3.2.  Comparison", "2.3.3.")
    rows = re.findall(r"^   \|(.+)\|$", old, flags=re.MULTILINE)
    cells = [[cell.strip() for cell in row.split("|")] for row in rows[1:]]
    assert cells == _table_3(rfc9110)
    for one, two, strong, weak in cells:
        assert strong_compare(one, two) is (strong == "match")
        assert weak_compare(one, two) is (weak == "match")


def test_the_examples_did_not_change(rfc7232: str, rfc9110: str) -> None:
    def indented(name: str) -> list[str]:
        return re.findall(rf"^     {name}: (.+)$", rfc7232, flags=re.MULTILINE)

    for name in ("ETag", "If-Match", "If-None-Match"):
        assert set(indented(name)) <= set(_field_lines(rfc9110, name)), name
        assert indented(name), name
        for field in indented(name):
            assert parse(field)


def test_the_precedence_did_not_change(rfc7232: str, rfc9110: str) -> None:
    old = _steps(rfc7232, "6.  Precedence", "7.  IANA Considerations")
    new = _steps(rfc9110, "13.2.2.  Precedence of Preconditions", "14.  Range Requests")
    for step in (
        "1. When recipient is the origin server and If-Match is present",
        "3. When If-None-Match is present, evaluate the If-None-Match precondition",
        "if false for GET/HEAD, respond 304 (Not Modified)",
        "if false for other methods, respond 412 (Precondition Failed)",
    ):
        assert step in old and step in new, step
