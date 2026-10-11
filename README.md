# etag

Create, parse and compare HTTP ETags per RFC 7232, zero dependencies and fully typed.

## Install

```
pip install etag
```

## Usage

```python
from etag import make_etag, parse, matches

# Build an entity-tag from a representation.
tag = make_etag(b"<html>...</html>")        # '"<sha-256 hex>"'
weak = make_etag(b"<html>...</html>", weak=True)  # 'W/"<sha-256 hex>"'

# Parse an ETag or If-None-Match / If-Match header.
parse('"a", W/"b"')   # [("a", False), ("b", True)]
parse("*")            # [("*", False)]

# Conditional request checks, with the right comparison per header.
matches('W/"a", "b"', '"a"')              # True  (If-None-Match: weak comparison)
matches('W/"a"', '"a"', weak=False)       # False (If-Match: strong comparison)
matches("*", tag)                          # True  (wildcard)
```

`make_etag(data, *, weak=False)` hashes `data` (bytes, or text encoded as UTF-8) with
SHA-256 and returns a quoted opaque-tag, optionally weak.

`parse(header)` returns a list of `(value, weak)` pairs, where `value` is the opaque-tag
without its quotes. A bare `*` wildcard yields `[("*", False)]`. Malformed input raises
`ValueError`.

`matches(header, etag, *, weak=True)` applies the RFC 7232 comparison rules. The default
weak comparison is the one `If-None-Match` uses: two tags are equivalent when their
opaque values match, regardless of either being weak. Pass `weak=False` for the strong
comparison `If-Match` uses, where both tags must be strong.

## Why

HTTP servers and caches lean on ETags constantly, yet every web framework carries its own
private copy of this logic. Werkzeug, Starlette and others each reimplement parsing and
the weak-versus-strong comparison internally, and there is no small, standalone, typed
package that does only this and does it correctly. `etag` fills that gap: a single module
with no runtime dependencies, exact RFC 7232 grammar and comparison, and `py.typed`
shipped.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
