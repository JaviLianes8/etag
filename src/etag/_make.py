"""Build an entity-tag from the bytes of a representation."""

from __future__ import annotations

import hashlib


def make_etag(data: bytes | str, *, weak: bool = False) -> str:
    """Return a quoted entity-tag derived from ``data``.

    ``data`` is hashed with SHA-256; text is encoded as UTF-8 first. The result is a
    double-quoted opaque-tag, prefixed with ``W/`` when ``weak`` is set.
    """
    raw = data.encode("utf-8") if isinstance(data, str) else data
    tag = f'"{hashlib.sha256(raw).hexdigest()}"'
    return f"W/{tag}" if weak else tag
