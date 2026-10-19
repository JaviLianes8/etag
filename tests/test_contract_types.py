"""Types are judged by what a value is, never by what it claims to be."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from test_contract_api import FLAG_CALLS

from etag import (
    EntityTag,
    evaluate_preconditions,
    format_etag,
    if_match,
    if_none_match,
    if_range,
    is_wildcard,
    make_etag,
    matches,
    parse,
    strong_compare,
    weak_compare,
)

FORGED = b'"forged", *'


class BufferBytes(bytes):
    """Bytes that export other octets through the buffer protocol (Python 3.12 and later)."""

    def __buffer__(self, flags: int) -> memoryview:
        return memoryview(FORGED)


class BufferArray(bytearray):
    def __buffer__(self, flags: int) -> memoryview:
        return memoryview(FORGED)

    def __release_buffer__(self, view: memoryview) -> None:
        pass


@pytest.mark.parametrize("kind", [BufferBytes, BufferArray])
def test_byte_subclasses_are_read_as_their_stored_octets(kind: type[bytes]) -> None:
    header = kind(b'"a"')
    assert parse(header) == parse([header]) == [EntityTag("a")]
    assert is_wildcard(header) is False
    assert if_match(header, '"a"') is True and if_none_match(header, '"a"') is False
    assert matches(header, '"forged"') is False and if_range(header, '"a"') is True
    assert evaluate_preconditions("PUT", '"a"', if_match=header) is None
    assert make_etag(header) == make_etag(b'"a"')
    assert make_etag(kind()) == make_etag(b"")


def _claiming(kind: type, **methods: Callable[..., Any]) -> Any:
    """An object whose ``__class__`` property claims ``kind``, with a 205-character name."""
    namespace: dict[str, Any] = {"__class__": property(lambda self: kind), **methods}
    return type("Claim" + "s" * 200, (), namespace)()


NAME = "Claim" + "s" * 35  # the type name cut to 40 characters


@pytest.mark.parametrize("truth", [True, False])
@pytest.mark.parametrize("call", FLAG_CALLS)
def test_a_value_claiming_to_be_a_bool_is_refused(
    call: Callable[[Any], object], truth: bool
) -> None:
    fake = _claiming(bool, __bool__=lambda self: truth)
    assert isinstance(fake, bool)
    with pytest.raises(TypeError, match=f"must be a bool, not {NAME}$"):
        call(fake)
    with pytest.raises(TypeError, match="exists must be a bool"):
        if_match("*", None, exists=fake)


CALLS: list[Callable[[Any], object]] = [
    parse,
    is_wildcard,
    lambda v: format_etag(v),
    lambda v: str(EntityTag(v)),
    lambda v: make_etag(v),
    lambda v: strong_compare(v, '"a"'),
    lambda v: weak_compare('"a"', v),
    lambda v: matches(v, '"a"'),
    lambda v: matches('"a"', v),
    lambda v: if_match(v, '"a"'),
    lambda v: if_none_match('"a"', v),
    lambda v: if_range(v, None),
    lambda v: evaluate_preconditions(v, None),
    lambda v: evaluate_preconditions("GET", None, if_match=v),
    lambda v: evaluate_preconditions("OPTIONS", None, if_none_match=v),
]


@pytest.mark.parametrize("kind", [str, bytes, bytearray, list, tuple, EntityTag])
@pytest.mark.parametrize("call", CALLS)
def test_a_value_claiming_another_type_gets_a_short_type_error(
    call: Callable[[Any], object], kind: type
) -> None:
    lines = {"__iter__": lambda self: iter(['"a"']), "__len__": lambda self: 1}
    fake = _claiming(kind, **lines)
    assert isinstance(fake, kind)
    with pytest.raises(TypeError) as caught:
        call(fake)
    message = str(caught.value)
    assert message.endswith(f"not {NAME}") and len(message) < 100, message


class CountedLines(list[str]):
    """Field lines that count how often they are iterated and claim to be empty."""

    def __init__(self, lines: list[str]) -> None:
        super().__init__(lines)
        self.reads = 0

    def __iter__(self) -> Iterator[str]:
        self.reads += 1
        return super().__iter__()

    def __len__(self) -> int:
        return 0


READERS: list[Callable[[Any], object]] = [
    parse,
    is_wildcard,
    lambda h: matches(h, '"b"'),
    lambda h: if_match(h, '"b"'),
    lambda h: if_none_match(h, '"b"'),
    lambda h: if_range(h, '"b"'),
    lambda h: evaluate_preconditions("PUT", '"b"', if_none_match=h),
]


@pytest.mark.parametrize("read", READERS)
def test_field_lines_are_read_once_by_iterating_them(read: Callable[[Any], object]) -> None:
    lines = CountedLines(['"b"'])
    read(lines)
    assert lines.reads == 1
    # A length of 0 does not make the field absent: the lines are what counts.
    assert evaluate_preconditions("PUT", '"a"', if_match=CountedLines(['"b"'])) == 412
