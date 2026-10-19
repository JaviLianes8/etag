# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-19

The public API is stable: `EntityTag`, `Header`, `evaluate_preconditions`, `format_etag`,
`if_match`, `if_none_match`, `if_range`, `is_wildcard`, `make_etag`, `matches`, `parse`,
`strong_compare` and `weak_compare` keep their names, signatures and defaults from
0.2.0, and their results on well-formed, well-typed input are unchanged except for the
two list readings under Changed (an empty list in `matches`, `*` among empty elements).
`parse("*")` still returns `[EntityTag("*")]`, equal to the parse of the tag `"*"`: this
is kept on purpose so that `parse` always returns `EntityTag` items, and `is_wildcard`
tells the two apart.

### Changed

- `weak` (in `format_etag`, `make_etag`, `matches` and the `weak` field of an
  `EntityTag` given to any function or to `str()`) and `exists` must be real bools;
  anything else raises `TypeError` instead of being read by its truth value.
- `evaluate_preconditions` raises `TypeError` for a `method` that is not text (0.2.0
  answered 412 for `b"GET"` where `"GET"` gets 304) and for a header that is neither `None`, text, bytes nor a
  list of them (0.2.0 took `0` or `False` for an absent field). Both header types are
  checked before anything is evaluated: for `CONNECT`, `OPTIONS` and `TRACE`, and for an
  If-None-Match that 0.2.0 never read once If-Match had failed.
- `matches` raises `ValueError` for a malformed header also when the target is weak and
  `weak=False` (0.2.0 returned `False`).
- `matches` returns `False` for a list with no member, such as `""`, `","` or `" , ,"`
  (0.2.0 raised `ValueError('no entity-tag found')`); `parse` still raises for them.
- `*` with only empty list elements around it (`"*, "`, `", *"`) is the wildcard for
  `is_wildcard`, `parse`, `matches` and the evaluators, as a list of field lines holding
  `*` and a blank line already was (0.2.0 read the string form as malformed, so the two
  forms gave opposite preconditions).
- A `memoryview` or an `array.array` passed as a header raises the header `TypeError`
  instead of being read as a list of field lines, which took a
  `memoryview(b"*").cast("c")` for the wildcard. A released `memoryview`, or a list
  whose `__buffer__` fails with `BufferError` (Python 3.12 and later), raises the same
  `TypeError`.
- The `EntityTag` signature reads `(value: str, weak: bool = False)` in `help()` and
  `inspect.signature` on every supported Python (it showed `ForwardRef` before 3.14).
- `make_etag` names the type in its `TypeError` for data that is neither text nor
  bytes-like, and raises a plain `ValueError` naming the code point for text holding a
  lone surrogate (0.2.0 raised `UnicodeEncodeError`, which carries the whole text).
- Subclasses of `str`, `bytes`, `bytearray` and `EntityTag` are read as the plain values
  they hold, so overridden methods (`__buffer__` included, on Python 3.12 and later)
  cannot change a result. Types are judged by what a value is: an object that only
  claims to be a bool, text, bytes, a list or an `EntityTag` through a `__class__`
  property raises `TypeError`.
- Each header argument is read once, a list of field lines by iterating it; a list that
  yields no line means the field is absent, whatever its `__len__` says.
- An `EntityTag` is never read as a list of field lines, and one built by hand with other
  than two fields raises `TypeError`.
- Public names report `etag` as their module (`etag.EntityTag` in reprs and pickles);
  the stray `annotations` attribute of the package is gone.
- Error messages: positions count from the start of the (joined) field value, not after
  its leading whitespace; `unterminated opaque-tag` and `expected a single entity-tag`
  now end with the position (`at position N`, `, more at position N`); `format_etag`
  says `U+XXXX is not allowed in an opaque-tag at N` instead of quoting the character
  and saying `at position N`; type names are cut to 40 characters.
- `Development Status :: 5 - Production/Stable`; Python 3.14 is listed; the sdist is
  built from an explicit file list.

### Added

- GUIDE.md: the grammar, the comparisons, conditional requests, every error, and how
  Werkzeug, Django, aiohttp, Starlette, jshttp/fresh and nginx differ.
- The `oracle` extra installs the reference implementations the tests compare with.

### Upgrading from 0.2.0

- Pass `weak=True`/`False` and `exists=True`/`False`/`None`, never `0`, `1` or strings.
- Pass the request method as `str` (decode bytes from ASGI first).
- Pass `None` or `[]` for a header the request did not carry.
- Code that matched error message text must expect the new wording and positions
  listed above; catching `ValueError` and `TypeError` works as before.

## [0.2.0] - 2026-10-12

### Added

- `evaluate_preconditions` returns 412, 304 or `None` for If-Match and If-None-Match in
  the order of RFC 9110 section 13.2.2.
- `if_match`, `if_none_match` and `if_range` follow the evaluation steps of RFC 9110
  sections 13.1.1, 13.1.2 and 13.1.5, including the wildcard against a missing
  representation and malformed field values.
- `EntityTag`, a `NamedTuple` of `(value, weak)` whose `str()` is the header form.
- `format_etag` quotes and validates a server-chosen opaque value.
- `strong_compare` and `weak_compare` expose the RFC 9110 comparison functions.
- `is_wildcard` tells `*` apart from the entity-tag `"*"`.
- Header arguments accept `bytes` (decoded as Latin-1) and lists of field lines; blank
  lines are dropped and an empty list means the field is absent. `Header` names the type.
- `exists=True` covers a resource that exists but is served without an entity-tag.
- `evaluate_preconditions` ignores the fields for `CONNECT`, `OPTIONS` and `TRACE`.

### Changed

- `parse` returns `EntityTag` items, which still unpack and compare as `(value, weak)`.
  Code annotated with `list[tuple[str, bool]]` needs `list[EntityTag]` or
  `Sequence[tuple[str, bool]]`, since `list` is invariant for type checkers.
- `matches('"*"', '"*"')` is `True`: the tag `"*"` is no longer mistaken for the wildcard.
- The `etag` argument of `matches` must be exactly one entity-tag; a trailing comma
  (`'"a",'`) now raises `ValueError`.
- References moved from RFC 7232 to RFC 9110, which obsoletes it.

### Fixed

- Entity-tags not separated by a comma (`"a" "b"`) are rejected.
- Empty list elements (`"a", , "b"`) are skipped, as recipients are required to do.
- Only spaces and tabs count as optional whitespace around a field value.
- `matches` validates its `etag` argument even when the header is the wildcard.

## [0.1.0]

- `make_etag` builds a quoted, optionally weak entity-tag from bytes or text.
- `parse` reads an ETag or If-None-Match / If-Match header into `(value, weak)` pairs,
  handling the wildcard and rejecting malformed input.
- `matches` applies the RFC 7232 weak and strong comparison rules for conditional
  requests.
