# etag improvement round

Progress:
- [x] Brainstorm ranked improvements (this file)
- [ ] Parser: comma-separated list rule, empty elements, OWS only, field lines, bytes
- [ ] `EntityTag` value type, `format_etag`, `strong_compare`, `weak_compare`, `is_wildcard`
- [ ] Conditional requests: `if_match`, `if_none_match`, `if_range`, `evaluate_preconditions`
- [ ] Contracts: RFC 9110 fixtures, grammar oracle, typing, README examples
- [ ] Installed wheel e2e test
- [ ] Docs: README, CHANGELOG, docstrings, packaging metadata
- [ ] Gates: ruff format, ruff check, mypy --strict, pytest
- [ ] Independent review findings fixed with regression tests
- [ ] Pull request opened, guard clean

Every item is additive. `make_etag`, `parse` and `matches` keep their names, their
arguments and their results (`parse` items still unpack and compare as `(value, weak)`).

## Starting point

`0.1.0` cites RFC 7232, which RFC 9110 obsoleted in 2022. Reading it against the
current text turned up these gaps:

- `parse('"a" "b"')` and `parse('"a""b"')` are accepted as two tags. The list rule
  requires a comma between elements.
- Surrounding whitespace is removed with `str.strip()`, so a no-break space or a vertical
  tab around the value is silently accepted. Only SP and HTAB are optional whitespace.
- `parse("*")` and `parse('"*"')` return the same thing, so a caller cannot tell the
  wildcard from a strong tag whose opaque value is `*`.
- The library compares tags but does not evaluate a condition. Every caller has to know
  that `If-Match: *` needs a current representation, that a malformed `If-Match` is
  false while a malformed `If-None-Match` is true, which one gives 304 and which 412,
  and the order in which the two fields are evaluated.
- A server that versions its resources (`"123-a"`) has no way to emit a validated tag;
  `make_etag` only hashes.
- Repeated field lines (`headers.get_all(...)`) and raw `bytes` values (ASGI) have to be
  joined and decoded by hand.

## Sources (fetched 2026-10-12)

- RFC 9110, HTTP Semantics: https://www.rfc-editor.org/rfc/rfc9110.txt
  - 8.8.3 ETag grammar and examples, 8.8.3.2 comparison table (Table 3),
    8.8.3.3 `"123-a"` / `"123-b"` example.
  - 13.1.1 If-Match and 13.1.2 If-None-Match: grammar, examples, evaluation steps.
  - 13.1.5 If-Range: strong comparison, weak tags never match.
  - 13.2.2 precedence: If-Match first (412), then If-None-Match (304 for GET/HEAD,
    412 otherwise).
  - 5.3 field order (lines joined with a comma), 5.5 obs-text, 5.6.1.2 recipient list
    rule (empty elements ignored), 5.6.3 OWS = SP / HTAB.

## Ranked improvements

1. **Correct list grammar.** Elements separated by a comma with SP/HTAB around it,
   empty elements ignored as 5.6.1.2 requires, the wildcard only on its own.
2. **Conditional request evaluation.** `if_match`, `if_none_match` and `if_range`
   follow the numbered evaluation steps of 13.1.1, 13.1.2 and 13.1.5, including the
   wildcard against "no current representation" and malformed values.
   `evaluate_preconditions` returns 412, 304 or `None` in the 13.2.2 order.
3. **Ground truth.** Every example of 8.8.3, 13.1.1 and 13.1.2 and every row of
   Table 3, copied from the fetched text with its URL. A grammar oracle, derived by
   hand from the ABNF and labelled as such, checked against random strings.
4. **`EntityTag` value type.** A `NamedTuple` (`value`, `weak`) that serialises with
   `str()`, so existing tuple unpacking keeps working.
5. **`format_etag`** quotes a server-chosen opaque value and rejects characters the
   grammar forbids. **`strong_compare` / `weak_compare`** expose Table 3 directly.
6. **`is_wildcard`** tells `*` apart from `"*"`.
7. **Field lines and bytes.** Every header argument also takes `bytes` (decoded as
   Latin-1, so obs-text survives) and a list of field lines, joined as 5.3 says.
8. **Typed public API, proven.** A test runs mypy on a snippet and checks the revealed
   types and that wrong argument types are rejected.
9. **Docs with runnable examples.** Every Python block in the README runs in the test
   suite. RFC 9110 everywhere, CHANGELOG entry, docstrings on every public name.
10. **Packaging.** Classifiers, keywords, a version-matches-metadata test and an
    installed-wheel e2e test.

## Out of scope

- A command line tool: an entity-tag is produced and checked inside a server, and
  `sha256sum` already prints a digest in the shell.
- If-Modified-Since, If-Unmodified-Since and the HTTP-date branch of If-Range: they
  need date parsing and the Date / Last-Modified pair, a separate concern. The
  evaluators document where a caller slots them in.
- Framework middleware: each framework already has a response object; this library
  stays the small piece they can share.
