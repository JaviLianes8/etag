"""Parse ETag and If-None-Match / If-Match header values per RFC 7232."""

from __future__ import annotations

WILDCARD = "*"


def _is_etagc(char: str) -> bool:
    """Report whether a character is allowed inside an opaque-tag (RFC 7232 etagc)."""
    code = ord(char)
    return code == 0x21 or 0x23 <= code <= 0x7E or 0x80 <= code <= 0xFF


def parse(header: str) -> list[tuple[str, bool]]:
    """Parse a header into a list of ``(value, weak)`` entity-tags.

    ``value`` is the opaque-tag without its surrounding quotes. ``weak`` is ``True`` when
    the tag carried the ``W/`` prefix. A bare ``*`` wildcard yields ``[("*", False)]``.
    Raises ``ValueError`` on malformed input.
    """
    text = header.strip()
    if text == WILDCARD:
        return [(WILDCARD, False)]

    entries: list[tuple[str, bool]] = []
    i, length = 0, len(text)
    while i < length:
        while i < length and text[i] in ", \t":
            i += 1
        if i >= length:
            break
        weak = False
        if text.startswith("W/", i):
            weak = True
            i += 2
        if i >= length or text[i] != '"':
            raise ValueError(f"expected an opaque-tag at position {i}")
        i += 1
        start = i
        while i < length and text[i] != '"':
            if not _is_etagc(text[i]):
                raise ValueError(f"invalid character in opaque-tag at position {i}")
            i += 1
        if i >= length:
            raise ValueError("unterminated opaque-tag")
        entries.append((text[start:i], weak))
        i += 1

    if not entries:
        raise ValueError("no entity-tag found")
    return entries


def parse_one(etag: str) -> tuple[str, bool]:
    """Parse a single entity-tag, rejecting lists and the wildcard."""
    entries = parse(etag)
    if len(entries) != 1 or entries[0][0] == WILDCARD:
        raise ValueError("expected a single entity-tag")
    return entries[0]
