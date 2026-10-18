# etag guide

How `etag` reads entity-tags, compares them and decides a conditional request, what it
raises, and where other implementations answer differently. Every code block on this
page runs in the test suite.

## The grammar

RFC 9110 section 8.8.3 defines an entity-tag as an optional, case-sensitive `W/` weak
marker followed by an opaque-tag: a double quote, any number of `etagc` characters and a
closing double quote. `etagc` is `!`, `#` to `~` and the obs-text range U+0080 to U+00FF,
so a space, a double quote or anything above U+00FF never appears inside. A backslash is
an ordinary character, since there are no escapes, and the first double quote after the
opening one closes the tag.

If-Match and If-None-Match carry either `*` or a comma-separated list of entity-tags.
Recipients skip empty list elements (section 5.6.1.2) and accept only spaces and tabs as
optional whitespace. `*` must stand alone: `*, "a"` is malformed.

```python
from etag import EntityTag, is_wildcard, parse

assert parse(' "a" ,, W/"b" ') == [EntityTag("a"), EntityTag("b", weak=True)]
assert parse('"a,b"') == [EntityTag("a,b")]  # a comma inside the quotes is data
assert is_wildcard("*") and not is_wildcard('"*"')
for bad in ['"a" "b"', 'w/"a"', '*, "a"', '"a b"', "a", ""]:
    try:
        parse(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(bad)
```

## Header arguments

Every header argument is a `Header`: text, `bytes` or `bytearray` (decoded as Latin-1,
the way ASGI servers hand header values over, so every octet maps to one character), or
a list of field lines. Field lines are joined in order with a comma as section 5.3
describes; blank lines are dropped first. Each header argument is read once, a list by
iterating it. In `evaluate_preconditions`, `None` or an empty list means the request did
not carry the field, while an empty string is a field that is present with an empty
value.

## Comparing entity-tags

Section 8.8.3.2 defines two comparison functions. The strong one matches only when both
tags are strong and their opaque values are identical; the weak one ignores the `W/`
marker. Comparisons are character by character: there is no case folding.

```python
from etag import matches, strong_compare, weak_compare

assert weak_compare('W/"1"', '"1"') and not strong_compare('W/"1"', '"1"')
assert not weak_compare('"a"', '"A"')
assert matches('"x", W/"a"', '"a"')  # weak, the If-None-Match rule
assert not matches('"x", W/"a"', '"a"', weak=False)  # strong, the If-Match rule
```

## Conditional requests

`if_match`, `if_none_match` and `if_range` follow the numbered steps of sections 13.1.1,
13.1.2 and 13.1.5 for an origin server. Pass the entity-tag of the selected
representation, or `None` when there is none; `exists=True` covers a resource that
exists but is served without a tag.

| Field | `*` | list | malformed | comparison | false means |
| --- | --- | --- | --- | --- | --- |
| If-Match | true if a representation exists | true if a member matches | false | strong | 412 |
| If-None-Match | false if a representation exists | false if a member matches | true | weak | 304 for GET and HEAD, else 412 |
| If-Range (tag form) | false | false | false | strong | ignore Range, send 200 |

`evaluate_preconditions` applies steps 1 and 3 of section 13.2.2 and returns 412, 304 or
`None`. It does not evaluate dates: when you support them, check If-Unmodified-Since
only when the request has no If-Match, If-Modified-Since only for GET and HEAD without
If-None-Match, and If-Range (date or tag form) only for a GET with a Range. Method names
are case-sensitive, and `CONNECT`, `OPTIONS` and `TRACE` ignore the fields (section
13.2.1). Section 13.1.1 also lets a server answer 2xx instead of 412 when a
state-changing request has visibly been applied already; that judgement stays yours.

```python
from etag import evaluate_preconditions, if_range, make_etag

current = make_etag(b"version 2")
assert evaluate_preconditions("GET", current, if_none_match=current) == 304
assert evaluate_preconditions("PUT", current, if_none_match=current) == 412
assert evaluate_preconditions("PUT", current, if_match='"stale"') == 412
assert evaluate_preconditions("PUT", None, if_none_match="*") is None  # create only
assert evaluate_preconditions("PUT", None, if_none_match="*", exists=True) == 412
assert evaluate_preconditions("GET", current, if_match=[], if_none_match=None) is None
assert evaluate_preconditions("PUT", current, if_match="") == 412  # present, no tags
assert if_range(current, current) and not if_range("W/" + current, current)
```

## Errors

Messages give a position or a type name (cut to 40 characters), never the input.

| Raised by | Exception | When |
| --- | --- | --- |
| `parse`, `matches` (header) | `ValueError` | malformed value; `expected an opaque-tag`, `unterminated opaque-tag`, `invalid character in opaque-tag` or `expected a comma` at a position in the joined value, or `no entity-tag found` |
| every function taking one tag | `ValueError` | the tag is malformed, a list, or `*`; also `expected a single entity-tag` |
| `format_etag`, `str(EntityTag)` | `ValueError` | `U+XXXX is not allowed in an opaque-tag` at an index |
| `if_match`, `if_none_match`, `evaluate_preconditions` | `ValueError` | `exists=False` together with a tag |
| `make_etag` | `ValueError` | `U+XXXX cannot be encoded as UTF-8` at an index: text holding a lone surrogate |
| `make_etag` | `BufferError` | a buffer that is not contiguous |
| `make_etag` | `ValueError` | a memoryview that was released |
| any function | `TypeError` | a header that is not text, bytes or a list of them; a tag that is not text or an `EntityTag`; an opaque value that is not text; `weak` or `exists` that is not a bool; a `method` that is not text; `make_etag` data that is neither text nor bytes-like |

The evaluators never raise for a malformed header: they return the outcome the RFC gives
to a malformed field. Use `parse` or `matches` when you want the error instead.

An exception raised by your own object while it is read (a list whose `__iter__`
raises, a buffer that refuses to export) reaches you unchanged, also for the methods that
ignore preconditions. An `EntityTag` is never taken for a list of field lines, and one
built by hand with other than two fields raises `TypeError`.

Subclasses of `str`, `bytes`, `bytearray` and `EntityTag` are read as the plain values
they hold, so overridden methods (`__buffer__` included) cannot change a result. Types
are judged by what a value is: an object that only claims a type through a `__class__`
property gets the `TypeError` of a wrong argument type.

## How other implementations differ

The tests run Werkzeug 3.1.9, Django 6.1.2, aiohttp 3.14.5, Starlette 1.8.0 and Node
v24.18.0 with jshttp/fresh 2.0.0 on the same 2,000 seeded field values and 3,000 seeded
requests (`tests/fixtures/oracle_runs.json`), and read the nginx 1.31.7 source. Each
difference below is asserted by `tests/test_references.py` or
`tests/test_references_more.py`; everything else agrees.

- Werkzeug `parse_etags`: same tags on every value `etag` accepts, except that `*` with
  whitespace around it is read as a tag named `*`, and the empty tag `""` is stored as
  `None`, so `is_resource_modified` never matches it. It also accepts many values the
  grammar rejects (unquoted members, a lower-case `w/`).
- Django `parse_etags` and `get_conditional_response`: the same status for every
  well-formed request, except that Django splits at every comma, even inside a tag like
  `"a,b"`. It drops malformed members, so a malformed If-Match can let a request through
  where `etag` answers 412, and a field left without valid members counts as absent.
- aiohttp: reads the same tags but stops at leading or trailing whitespace (`'"a" '`
  reads no tag at all), an empty element or the empty tag `""`; accepts any regular
  expression whitespace around commas, vertical tab and CR LF included, where the
  grammar allows only spaces and tabs; accepts `*` only without whitespace; and takes a
  list holding only the tag `"*"` for the wildcard.
- Starlette `StaticFiles.is_not_modified`: the same answer for every well-formed
  If-None-Match without a comma inside a tag.
- jshttp/fresh: the same answer where its tokenizer can read the value; it splits at
  every comma, trims spaces but not tabs, and takes `*` only without whitespace.
- nginx: evaluates If-Match before If-None-Match, answering 412 and 304, the same order
  as section 13.2.2. Its If-None-Match comparison drops `W/` on both sides (weak); its
  If-Match comparison is byte for byte, `W/` included, so `If-Match: W/"a"` matches a
  current `W/"a"` where the strong comparison fails; and it takes `*` only without
  whitespace.

## RFC 7232

RFC 9110 obsoletes RFC 7232, the reference of `etag` 0.1. The grammar, the comparison
table and the order of evaluation are the same in both, and every example of RFC 7232 is
also in RFC 9110, which adds one more `ETag` example (section 3.9);
`tests/test_rfc7232.py` checks this against the fetched texts.

## Upgrading from 0.2.0

Results on well-typed input are unchanged except for `matches`, which now raises for a
malformed header also when the target is weak and `weak=False`, and for subclasses that
override methods of `str`, `bytes` or `EntityTag`, which are now read as plain values.
Error positions now count from the start of the field value, not after its leading
whitespace. Arguments of the wrong
type now raise `TypeError` where 0.2.0 guessed: `weak` and `exists` must be real bools,
`method` must be text, and a header such as `0` is no longer taken for an absent field.
The full list is in the [changelog](https://github.com/JaviLianes8/etag/blob/main/CHANGELOG.md).
