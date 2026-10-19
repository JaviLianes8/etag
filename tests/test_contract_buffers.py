"""Contracts for buffer objects: headers reject them, make_etag documents its errors."""

from __future__ import annotations

import array
import sys
from collections.abc import Callable, Iterator, Sequence

import pytest

from etag import (
    evaluate_preconditions,
    if_match,
    if_none_match,
    if_range,
    is_wildcard,
    make_etag,
    matches,
    parse,
)


def _buffers() -> list[object]:
    return [
        memoryview(b"*"),
        memoryview(b"*").cast("c"),
        memoryview(b'"a"'),
        array.array("I", [0x22, 0x61, 0x22]),
        array.array("B", b"*"),
    ]


READERS: dict[str, Callable[[object], object]] = {
    "parse": lambda header: parse(header),  # type: ignore[arg-type]
    "is_wildcard": lambda header: is_wildcard(header),  # type: ignore[arg-type]
    "matches": lambda header: matches(header, '"a"'),  # type: ignore[arg-type]
    "if_match": lambda header: if_match(header, '"a"'),  # type: ignore[arg-type]
    "if_none_match": lambda header: if_none_match(header, '"a"'),  # type: ignore[arg-type]
    "if_range": lambda header: if_range(header, '"a"'),  # type: ignore[arg-type]
    "evaluate if_match": lambda header: evaluate_preconditions(
        "PUT",
        '"a"',
        if_match=header,  # type: ignore[arg-type]
    ),
    "evaluate if_none_match": lambda header: evaluate_preconditions(
        "GET",
        '"a"',
        if_none_match=header,  # type: ignore[arg-type]
    ),
}


@pytest.mark.parametrize("index", range(len(_buffers())))
@pytest.mark.parametrize("reader", sorted(READERS))
def test_a_buffer_header_is_a_header_level_type_error(reader: str, index: int) -> None:
    header = _buffers()[index]
    with pytest.raises(TypeError, match=r"^header must be str, bytes or a list of them, not "):
        READERS[reader](header)


def _released() -> memoryview:
    view = memoryview(b'"a"')
    view.release()
    return view


class _RefusingBuffer:
    """A list of one field line whose buffer export fails, as a busy buffer's does."""

    def __getitem__(self, index: int) -> str:
        return ['"a"'][index]

    def __len__(self) -> int:
        return 1

    def __iter__(self) -> Iterator[str]:
        return iter(['"a"'])

    def __buffer__(self, flags: int) -> memoryview:
        raise BufferError("export refused")


Sequence.register(_RefusingBuffer)


@pytest.mark.parametrize("reader", sorted(READERS))
def test_a_released_memoryview_header_is_a_header_level_type_error(reader: str) -> None:
    with pytest.raises(TypeError, match=r"^header must be str, bytes or a list of them, not "):
        READERS[reader](_released())


@pytest.mark.skipif(sys.version_info < (3, 12), reason="__buffer__ is honoured from 3.12")
@pytest.mark.parametrize("reader", sorted(READERS))
def test_a_header_that_refuses_to_export_its_buffer_is_still_a_buffer(reader: str) -> None:
    # Exporting a buffer at all makes it bytes-like, not a list of field lines, even
    # when the export itself fails.
    with pytest.raises(TypeError, match=r"^header must be str, bytes or a list of them, not "):
        READERS[reader](_RefusingBuffer())


def test_make_etag_lets_a_refused_buffer_export_reach_the_caller() -> None:
    if sys.version_info < (3, 12):
        pytest.skip("__buffer__ is honoured from 3.12")
    with pytest.raises(BufferError, match=r"^export refused$"):
        make_etag(_RefusingBuffer())


def test_a_buffer_field_line_is_a_field_line_type_error() -> None:
    with pytest.raises(TypeError, match=r"^field line must be str or bytes, not memoryview$"):
        parse(['"a"', memoryview(b'"b"')])  # type: ignore[list-item]


def test_make_etag_raises_buffer_error_for_a_non_contiguous_buffer() -> None:
    with pytest.raises(BufferError):
        make_etag(memoryview(b"abcd")[::2])


def test_make_etag_raises_value_error_for_a_released_memoryview() -> None:
    view = memoryview(b"abc")
    view.release()
    with pytest.raises(ValueError, match="released"):
        make_etag(view)


def test_make_etag_documents_both_buffer_errors() -> None:
    assert make_etag.__doc__ is not None
    assert "BufferError" in make_etag.__doc__
    assert "released" in make_etag.__doc__
