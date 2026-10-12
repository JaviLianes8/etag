# etag

Create, parse and compare HTTP entity-tags and evaluate conditional requests, exactly as
RFC 9110 defines them. Zero dependencies, fully typed.

## Install

```
pip install etag
```

## Evaluate a conditional request

`evaluate_preconditions` applies If-Match and If-None-Match in the order RFC 9110
section 13.2.2 requires and tells you which status to send, or `None` to go ahead.

```python
from etag import evaluate_preconditions, make_etag

body = b"<h1>Hello</h1>"
current = make_etag(body)

# A browser revalidating its cached copy gets a 304.
print(evaluate_preconditions("GET", current, if_none_match=current))  # 304

# A PUT based on an old version is refused with 412 (the "lost update" guard).
print(evaluate_preconditions("PUT", current, if_match='"old"'))  # 412

# "If-None-Match: *" on a PUT creates only when nothing exists yet.
print(evaluate_preconditions("PUT", None, if_none_match="*"))  # None (go ahead)
```

Pass the selected representation's entity-tag, or `None` when the resource has no
current representation. A resource that exists but is served without an entity-tag
passes `etag=None, exists=True`. Header arguments take text, `bytes` (decoded as
Latin-1, as ASGI servers hand them over) or a list of field lines, which are joined in
order as section 5.3 says; `None` or an empty list means the request did not carry the
field. `CONNECT`, `OPTIONS` and `TRACE` ignore preconditions (section 13.2.1). If you also support dates, check If-Unmodified-Since only when there
is no If-Match, and If-Modified-Since only when there is no If-None-Match.

## Each condition on its own

```python
from etag import if_match, if_none_match, if_range

assert if_match('"a", "b"', '"b"')  # strong comparison
assert not if_match('W/"b"', '"b"')  # a weak tag never satisfies If-Match
assert not if_none_match('W/"b"', '"b"')  # weak comparison: still a match
assert if_none_match("*", None)  # nothing exists yet
assert if_range('"b"', '"b"') and not if_range('W/"b"', '"b"')
```

The evaluators follow the numbered steps of sections 13.1.1, 13.1.2 and 13.1.5, so a
malformed If-Match is false and a malformed If-None-Match is true. `if_range` handles
the entity-tag form; an HTTP-date value returns `False` (send the whole
representation), so evaluate the date form yourself first if you accept it.

## Build entity-tags

```python
from etag import EntityTag, format_etag, make_etag

print(make_etag(b"abc")[:11])  # "ba7816bf8f
print(make_etag("abc", weak=True)[:5])  # W/"ba
print(format_etag("123-a"))  # "123-a"
print(EntityTag("123-a", weak=True))  # W/"123-a"
```

`make_etag` hashes bytes (or UTF-8 text) with SHA-256. `format_etag` quotes a value you
chose yourself, such as a revision number, and raises `ValueError` for any character
the grammar forbids, so a value can never break out of its header.

## Parse and compare

```python
from etag import EntityTag, is_wildcard, matches, parse, strong_compare, weak_compare

tags = parse('"a", , W/"b"')
assert tags == [EntityTag("a"), EntityTag("b", weak=True)]
value, weak = tags[1]  # still unpacks as (value, weak)

assert is_wildcard("*") and not is_wildcard('"*"')
assert parse(['"a"', b'"b"']) == [("a", False), ("b", False)]

assert weak_compare('W/"1"', '"1"') and not strong_compare('W/"1"', '"1"')
assert matches('W/"a", "b"', '"a"')  # If-None-Match rule
assert not matches('W/"a"', '"a"', weak=False)  # If-Match rule
```

`parse` skips empty list elements, requires a comma between tags, accepts only spaces
and tabs as optional whitespace and the `*` wildcard only on its own, and raises
`ValueError` on anything else. `matches` raises too; the evaluators above apply the RFC
outcome for malformed requests instead.

## API

| Name | Purpose |
| --- | --- |
| `make_etag(data, *, weak=False)` | SHA-256 entity-tag of bytes or text |
| `format_etag(value, *, weak=False)` | quote and validate an opaque value |
| `EntityTag(value, weak=False)` | parsed tag, a `NamedTuple`; `str()` gives the header form |
| `parse(header)` | list of `EntityTag`, `ValueError` when malformed |
| `is_wildcard(header)` | `True` only for `*` |
| `strong_compare(a, b)`, `weak_compare(a, b)` | section 8.8.3.2 comparisons |
| `matches(header, etag, *, weak=True)` | is `etag` in the list |
| `if_match`, `if_none_match`, `if_range` | evaluate one condition |
| `evaluate_preconditions(method, etag, *, if_match=None, if_none_match=None, exists=None)` | 412, 304 or `None` |
| `Header` | type of every header argument: `str`, `bytes` or a list of field lines |

## Why

HTTP servers and caches lean on entity-tags constantly, yet every web framework carries
its own private copy of this logic, and the subtle parts (comma rules, strong versus
weak comparison, which status and in which order) differ between them. `etag` is a
small standalone package that does only this, checked against the examples and the
comparison table of RFC 9110.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
