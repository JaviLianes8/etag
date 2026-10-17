"""Ground truth read from RFC 9110 and RFC 5234 as fetched by scripts/fetch_upstream.py.

Every example, table row and grammar rule below is taken from the fetched files when the
test runs (see tests/upstream/MANIFEST.json for the URLs and hashes); the tests skip when
the files are absent. Nothing here is transcribed by hand.
"""

from __future__ import annotations

import re

import pytest
from conftest import rule, section

from etag import (
    EntityTag,
    evaluate_preconditions,
    format_etag,
    if_match,
    if_none_match,
    is_wildcard,
    parse,
    strong_compare,
    weak_compare,
)


def code_points(rfc: str, name: str, *, depth: int = 0) -> set[int]:
    """The code points an ABNF rule of single characters admits, resolving named rules."""
    found: set[int] = set()
    for alternative in rule(rfc, name).split("/"):
        token = alternative.strip()
        if match := re.fullmatch(r"%x([0-9A-F]+)(?:-([0-9A-F]+))?", token):
            low = int(match.group(1), 16)
            found.update(range(low, int(match.group(2) or match.group(1), 16) + 1))
        elif match := re.fullmatch(r'"(.)"', token):
            found.add(ord(match.group(1)))
        else:
            assert depth < 3 and re.fullmatch(r"[\w-]+", token), token
            found |= code_points(rfc, token, depth=depth + 1)
    return found


def _accepted(char: str) -> bool:
    try:
        format_etag(char)
    except ValueError:
        return False
    return True


def test_etagc_is_the_abnf_set_for_every_code_point(rfc9110: str) -> None:
    allowed = code_points(rfc9110, "etagc")
    assert allowed == {0x21, *range(0x23, 0x7F), *range(0x80, 0x100)}
    for code in range(0x110000):
        assert _accepted(chr(code)) is (code in allowed), hex(code)


def test_the_entity_tag_rules_are_the_ones_implemented(rfc9110: str, rfc5234: str) -> None:
    assert rule(rfc9110, "entity-tag").split() == ["[", "weak", "]", "opaque-tag"]
    assert rule(rfc9110, "opaque-tag").split() == ["DQUOTE", "*etagc", "DQUOTE"]
    assert rule(rfc5234, "DQUOTE").split() == ["%x22"]
    # %s marks a case-sensitive string (RFC 7405): only an upper-case W is weak.
    assert rule(rfc9110, "weak").strip() == '%s"W/"'
    assert parse('W/"a"') == [EntityTag("a", True)]
    with pytest.raises(ValueError):
        parse('w/"a"')


def _field_lines(text: str, name: str) -> list[str]:
    return re.findall(rf"^   {name}: (.+)$", text, flags=re.MULTILINE)


def test_every_etag_example_parses_and_serialises_back(rfc9110: str) -> None:
    examples = _field_lines(rfc9110, "ETag")
    assert len(examples) == 6
    for field in examples:
        (tag,) = parse(field)
        assert str(tag) == field
        assert tag.weak is field.startswith("W/")


def _table_3(text: str) -> list[list[str]]:
    table = section(text, "8.8.3.2.  Comparison", "8.8.3.3.")
    rows = re.findall(r"^   \|(.+)\|$", table, flags=re.MULTILINE)
    return [[cell.strip() for cell in row.split("|")] for row in rows[1:]]


def test_table_3_comparisons_in_both_orders(rfc9110: str) -> None:
    rows = _table_3(rfc9110)
    assert len(rows) == 4
    for one, two, strong, weak in rows:
        assert strong_compare(one, two) is strong_compare(two, one) is (strong == "match")
        assert weak_compare(one, two) is weak_compare(two, one) is (weak == "match")


def test_if_match_examples(rfc9110: str) -> None:
    examples = _field_lines(rfc9110, "If-Match")
    assert len(examples) == 3 and examples[-1] == "*"
    for field in examples:
        assert if_match(field, '"xyzzy"') is True
        assert if_match(field, 'W/"xyzzy"') is (field == "*")
        assert len(parse(field)) == max(1, field.count('"') // 2)


def test_if_none_match_examples(rfc9110: str) -> None:
    examples = _field_lines(rfc9110, "If-None-Match")
    assert len(examples) == 5 and examples[-1] == "*"
    for field in examples:
        assert is_wildcard(field) is (field == "*")
        assert if_none_match(field, '"xyzzy"') is False
        assert if_none_match(field, 'W/"xyzzy"') is False
        assert if_none_match(field, '"other"') is (field != "*")


def _list_examples(text: str) -> tuple[list[str], list[str]]:
    body = section(text, "5.6.1.2.  Recipient Requirements", "5.6.2.")
    valid, invalid = body.split("In contrast", 1)
    pattern = r'^     "(.*)"$'
    return re.findall(pattern, valid, re.MULTILINE), re.findall(pattern, invalid, re.MULTILINE)


def test_the_list_examples_with_each_token_quoted(rfc9110: str) -> None:
    # The RFC examples are token lists; quoting every token turns them into tag lists.
    valid, invalid = _list_examples(rfc9110)
    assert len(valid) == 3 and len(invalid) == 3
    for example in valid:
        field = re.sub(r"[a-z]+", lambda m: f'"{m.group()}"', example)
        assert [tag.value for tag in parse(field)] == re.findall(r"[a-z]+", example)
    for example in invalid:
        with pytest.raises(ValueError, match="no entity-tag"):
            parse(example)


def _steps(text: str, start: str, end: str) -> str:
    return " ".join(section(text, start, end).split())


def test_the_evaluation_steps_are_the_ones_implemented(rfc9110: str) -> None:
    matching = _steps(rfc9110, "13.1.1.  If-Match", "13.1.2.")
    assert "the condition is true if any of the listed tags match" in matching
    assert "3. Otherwise, the condition is false." in matching
    none_matching = _steps(rfc9110, "13.1.2.  If-None-Match", "13.1.3.")
    assert "3. Otherwise, the condition is true." in none_matching
    assert if_match("not a list", '"a"') is False
    assert if_none_match("not a list", '"a"') is True


def test_the_precedence_is_the_one_implemented(rfc9110: str) -> None:
    order = _steps(rfc9110, "13.2.2.  Precedence of Preconditions", "14.  Range Requests")
    first = order.index("If-Match is present, evaluate the If-Match precondition")
    third = order.index("When If-None-Match is present, evaluate")
    assert first < third
    assert "if false for GET/HEAD, respond 304 (Not Modified)" in order
    assert "if false for other methods, respond 412 (Precondition Failed)" in order
    when = _steps(rfc9110, "13.2.1.  When to Evaluate", "13.2.2.")
    assert "such as CONNECT, OPTIONS, or TRACE" in when
    assert evaluate_preconditions("GET", '"a"', if_match='"b"', if_none_match='"a"') == 412
    assert evaluate_preconditions("HEAD", '"a"', if_none_match='"a"') == 304
    assert evaluate_preconditions("DELETE", '"a"', if_none_match='"a"') == 412
    for method in ("CONNECT", "OPTIONS", "TRACE"):
        assert evaluate_preconditions(method, '"a"', if_match='"b"') is None
