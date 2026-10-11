"""Create, parse and compare HTTP ETags per RFC 7232, zero dependencies and fully typed."""

from __future__ import annotations

from ._compare import matches
from ._make import make_etag
from ._parse import parse

__version__ = "0.1.0"

__all__ = ["make_etag", "matches", "parse"]
