# etag 1.0.0 certification report

Progress:
- [x] Branch `release/1.0.0` created from `main` (0.2.0, 2751382; PyPI has 0.2.0 only)
- [x] Baseline gates run on 0.2.0
- [x] API review and 1.0.0 API changes (item 1)
- [x] Real ground truth: fetched sources and live reference implementations (item 7)
- [x] Errors, typing, docstrings and doctests (items 2 to 5)
- [x] Contract, fuzz and author mutation round (items 6, 9, 18)
- [x] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [x] Packaging, e2e and upgrade from PyPI 0.2.0 (items 8, 10, 13, 14), author run
- [x] Second preparation pass: types judged by the real type, buffer-safe byte subclasses,
  headers read once, Express and jshttp/fresh vectors, release script, certified badge
- [x] Second pass verified: gates, full suite with e2e, every Python, mutations, long fuzz
- [ ] Five QA lenses report PASS (item 19)
- [ ] Independent reviewer reports PASS (item 16)
- [x] Gates (item 15), final run (author)
- [ ] PR and trace guard CLEAN (item 17); merge and publish left to the maintainer

## Baseline on 0.2.0 (before any change)

Fresh clone of `main` (2751382) on Elena's PC, CPython 3.14: `ruff format --check .`,
`ruff check .` and `mypy --strict src tests` exit 0; `pytest` with `ETAG_E2E=1` 190
passed. PyPI has 0.2.0 only.

Defects of 0.2.0 found by the API review:

- `weak` and `exists` were read by their truth value: `format_etag("a", weak="no")`
  gave `W/"a"`.
- `evaluate_preconditions(b"GET", ...)` answered 412 where `"GET"` gets 304, and a
  falsy header such as `0` was taken for an absent field.
- `matches('"a" "b"', 'W/"a"', weak=False)` returned `False` instead of raising for the
  malformed header, against its own docstring.
- Subclasses of `str`, `bytes` and `EntityTag` could steer every result through
  overridden methods (`strip`, `find`, `__iter__`, `__eq__`, properties).
- Type names in messages were unbounded; public names reported private modules; the
  package leaked an `annotations` attribute.
- Error positions were counted after trimming leading whitespace.
- The RFC fixtures were embedded in the test file with no fetch script or manifest, the
  README linked LICENSE relatively, there was no GUIDE and the sdist took every file not
  ignored by git.

## API review (item 1)

All thirteen public names keep their names, signatures and defaults; results on
well-formed, well-typed input are unchanged (checked by the upgrade test on 88,000
seeded calls). Changed, each in CHANGELOG 1.0.0 with an upgrade list: real bools for
`weak` and `exists`, text for `method`, a `TypeError` for headers of another type
(also for the methods that ignore preconditions), `matches` raising for a malformed
header whatever the target, subclasses read as plain values, public names reporting
`etag`, bounded type names, positions from the start of the field value. Considered and
kept: plain `ValueError` and `TypeError` rather than a new exception class (a subclass
of `ValueError` can still be added in a minor release); an empty If-Match string means
"present, no tags" and gives 412 (RFC 9110 `#entity-tag` with zero members matches
nothing), while `None` or `[]` means absent; `Header` stays a type alias.

## Ground truth (item 7)

`scripts/fetch_upstream.py` downloads nine sources into the git-ignored
`tests/upstream/` and checks them against `tests/upstream/MANIFEST.json` (URL, pinned
revision, fetch date 2026-10-17, size, SHA-256, licence): RFC 9110, RFC 7232, RFC 5234,
Werkzeug 3.1.9 `tests/test_http.py`, Django 6.1.2 `tests/utils_tests/test_http.py` and
`tests/conditional_processing/tests.py`, jshttp/fresh 2.0.0 `index.js` and `test/fresh.js`,
and nginx 1.31.7 `ngx_http_not_modified_filter_module.c`. Nothing fetched is committed
or shipped.

- `tests/test_rfc9110.py`: `etagc` evaluated from the ABNF in the fetched RFC 9110 and
  compared with `format_etag` for all 1,114,112 code points; the `entity-tag`,
  `opaque-tag` and case-sensitive `weak` rules; the six `ETag` examples, Table 3 in both
  orders, the If-Match and If-None-Match examples and the section 5.6.1.2 list examples,
  each read from the fetched text; the evaluation and precedence sentences of 13.1.1,
  13.1.2, 13.2.1 and 13.2.2 found in the text and checked against the behaviour.
- `tests/test_rfc7232.py`: RFC 7232 has the same `etagc` set, the same comparison table,
  examples that are a subset of RFC 9110's and the same precedence steps.
- `tests/test_upstream_vectors.py`: Werkzeug's `quote_etag`, `unquote_etag` and
  `parse_etags` vectors and Django's three `parse_etags` vectors, extracted from the
  fetched files with `ast`; sixteen scenarios of Django's conditional processing tests
  (transcribed by hand, labelled, with the tag constants read from the fetched file).
- `tests/test_references.py` and `tests/test_references_more.py` with
  `tests/fixtures/oracle_runs.json` (program output recorded by
  `scripts/oracle_fixture.py`: CPython 3.13.2, Werkzeug 3.1.9, Django 6.1.2, aiohttp
  3.14.5, Starlette 1.8.0, Node v24.18.0 with fresh 2.0.0; 2,000 seeded field values and
  3,000 seeded requests). Django's `get_conditional_response` gives the same status on
  every well-formed request (2,284 compared); Starlette agrees on every well-formed
  If-None-Match; Werkzeug, aiohttp and fresh agree outside named, counted differences
  (padded wildcard, the empty tag, commas inside tags, tabs, aiohttp's star tag); the
  nginx source evaluates If-Match strongly before If-None-Match weakly. The Python tools
  and fresh are rerun live when installed (`pip install etag[oracle]`) and give the
  recorded answers.

## Errors, typing, docs (items 2 to 5)

`__all__` lists the thirteen names and `dir()` exposes nothing else public; every public
function and class has a runnable docstring example (24 examples, plus the package
docstring), run by `tests/test_docs.py`, which also runs every README and GUIDE example.
`mypy --strict src tests scripts` is clean, `py.typed` ships, no `Any` in the public API.
GUIDE lists every error; messages carry a position or a type name cut to 40 characters,
never the input (checked on 1 MB hostile inputs).

## Contracts, fuzz and mutations (items 6, 9, 18)

New contract files: `test_contract_api.py` (signatures, module names, pickling, option
and argument types, documented messages), `test_contract_hostile.py` (lying subclasses,
metaclass names, bounded messages, linear time on 20,000 to 200,000 element inputs),
`test_properties.py` (36,000 seeded checks tying the evaluators to the comparisons and
a no-crash fuzz of every name with 12,000 values), plus the reference and RFC files above.

Author mutation round: 70 mutations over every module, each applied alone to a fresh
clone of the pushed branch (43480e9 for the first batch, df75331 for the rest) on Elena's
PC and the laptop, CPython 3.14, suite with `-x`, no bytecode, 300-second timeout, the
end-to-end modules left out; baseline green before and after each batch.

| Id | Module | Mutation | Caught by |
| --- | --- | --- | --- |
| T01 | `_tag` | etagc drops ! | `test_properties::test_tags_round_trip_through_their_header_form` |
| T02 | `_tag` | etagc takes DQUOTE | `test_rfc9110::test_etagc_is_the_abnf_set_for_every_code_point` |
| T03 | `_tag` | etagc takes DEL | `test_grammar::test_characters_outside_etagc_are_rejected[\x7f]` |
| T04 | `_tag` | etagc drops obs-text | `test_compare::test_comparisons_are_character_by_character` |
| T05 | `_tag` | etagc takes U+0100 | `test_grammar::test_characters_outside_etagc_are_rejected[\u0100]` |
| T06 | `_tag` | weak prefix lower case | `test_docs::test_every_readme_example_runs_and_prints_its_comment` |
| T07 | `_tag` | format_etag skips the flag check | `test_contract_api::test_options_must_be_real_bools[<lambda>0-0]` |
| T08 | `_tag` | format_etag reads a subclass through its methods | `test_contract_hostile::test_text_subclasses_are_read_as_their_characters` |
| T09 | `_tag` | make_etag drops weak | `test_docs::test_every_readme_example_runs_and_prints_its_comment` |
| T10 | `_tag` | make_etag encodes text as UTF-16 | `test_contract_hostile::test_text_subclasses_are_read_as_their_characters` |
| T11 | `_tag` | make_etag uses SHA-1 | `test_docs::test_every_readme_example_runs_and_prints_its_comment` |
| T12 | `_tag` | make_etag skips the flag check | equivalent (see below) |
| T13 | `_tag` | make_etag encodes through the subclass | `test_contract_hostile::test_text_subclasses_are_read_as_their_characters` |
| T14 | `_tag` | make_etag raises ValueError for a bad type | `test_contract_api::test_make_etag_hashes_any_contiguous_buffer` |
| T15 | `_tag` | format_etag error index off by one | `test_contract_api::test_error_messages_give_the_documented_positions` (added) |
| P01 | `_plain` | type name not bounded | `test_contract_hostile::test_type_names_in_messages_are_bounded` |
| P02 | `_plain` | type name through the metaclass | `test_contract_hostile::test_type_names_in_messages_are_bounded` (added) |
| P03 | `_plain` | text keeps the subclass | `test_contract_hostile::test_text_subclasses_are_read_as_their_characters` |
| P04 | `_plain` | bytes read as UTF-8 | `test_grammar::test_bytes_are_decoded_as_latin_1` |
| P05 | `_plain` | flags accept int | `test_contract_api::test_options_must_be_real_bools[<lambda>0-0]` |
| P06 | `_plain` | bytearray read as UTF-8 | `test_grammar::test_bytes_are_decoded_as_latin_1` (added) |
| R01 | `_parse` | wildcard trims any whitespace | `test_oracle::test_random_fields_agree_with_the_grammar[0]` |
| R02 | `_parse` | field lines joined without a comma | `test_compare::test_matches_reads_field_lines_and_bytes` |
| R03 | `_parse` | whitespace-only lines kept | `test_grammar::test_blank_field_lines_are_dropped_before_joining` |
| R04 | `_parse` | weak marker case-insensitive | `test_conditional::test_a_malformed_if_none_match_is_true[w/"a"]` |
| R05 | `_parse` | etagc not checked on the last character | `test_contract_api::test_error_messages_give_the_documented_positions[<lambda>-invalid` |
| R06 | `_parse` | adjacent tags accepted | `test_compare::test_matches_raises_on_a_malformed_header` |
| R07 | `_parse` | empty element skips a character | `test_grammar::test_the_rfc_list_examples_are_accepted["foo","bar"-values0]` |
| R08 | `_parse` | an empty list accepted | `test_contract_api::test_matches_rejects_a_malformed_list_whatever_the_target` |
| R09 | `_parse` | LF counted as whitespace | `test_grammar::test_other_whitespace_is_not_optional_whitespace["a"\n]` |
| R10 | `_parse` | wildcard read as a weak tag | `test_etag::test_parse_reads_the_wildcard` |
| R11 | `_parse` | single tag with trailing text accepted | `test_compare::test_comparisons_reject_anything_but_one_entity_tag["a",` |
| R12 | `_parse` | EntityTag weak accepts int | equivalent (see below) |
| R13 | `_parse` | EntityTag subclass returned as is | `test_contract_hostile::test_text_subclasses_are_read_as_their_characters` |
| R14 | `_parse` | bad field line raises ValueError | `test_contract_api::test_a_header_of_another_type_raises_type_error[header6]` |
| R15 | `_parse` | bytes header read as UTF-8 | `test_grammar::test_bytes_are_decoded_as_latin_1` |
| R16 | `_parse` | leading whitespace refused in one tag | `test_conditional::test_if_range_matches_only_an_identical_strong_tag` |
| R17 | `_parse` | unterminated tag position wrong | `test_contract_api::test_error_messages_give_the_documented_positions[<lambda>-unterminated` |
| R18 | `_parse` | comma error position off by one | `test_contract_api::test_error_messages_give_the_documented_positions[<lambda>-expected` |
| R19 | `_parse` | opaque value read from the subclass field | `test_contract_hostile::test_entity_tag_subclasses_are_read_as_their_fields` |
| C01 | `_compare` | strong compare ignores the left weak flag | `test_docs::test_every_readme_example_runs_and_prints_its_comment` |
| C02 | `_compare` | weak compare looks at the flags | `test_compare::test_comparisons_take_entity_tag_values` |
| C03 | `_compare` | matches: wildcard matches nothing | `test_etag::test_matches_wildcard_matches_any_tag` |
| C04 | `_compare` | matches: strong rule ignores weak members | `test_compare::test_matches_reads_field_lines_and_bytes` |
| C05 | `_compare` | matches: weak target matches strongly | `test_compare::test_matches_with_a_weak_target_never_matches_strongly` |
| C06 | `_compare` | matches: header not parsed for a weak target | `test_contract_api::test_matches_rejects_a_malformed_list_whatever_the_target` |
| C07 | `_compare` | matches skips the flag check | `test_contract_api::test_options_must_be_real_bools[<lambda>2-0]` |
| D01 | `_conditional` | If-Match accepts a weak current tag | `test_conditional::test_if_match_uses_the_strong_comparison` |
| D02 | `_conditional` | malformed If-Match is true | `test_conditional::test_a_malformed_if_match_is_false["a"` |
| D03 | `_conditional` | If-None-Match uses the strong comparison | `test_conditional::test_if_none_match_uses_the_weak_comparison` |
| D04 | `_conditional` | If-None-Match wildcard inverted | `test_conditional::test_if_none_match_without_a_representation` |
| D05 | `_conditional` | malformed If-None-Match is false | `test_conditional::test_a_malformed_if_none_match_is_true["a"` |
| D06 | `_conditional` | If-Range accepts a weak validator | `test_conditional::test_if_range_matches_only_an_identical_strong_tag` |
| D07 | `_conditional` | If-Range takes the first tag of a list | `test_conditional::test_if_range_is_false_for_anything_but_one_entity_tag["a",` |
| D08 | `_conditional` | 304 for every method | `test_conditional::test_evaluate_preconditions_follows_section_13_2_2[POST-"a"-None-"a"-412]` |
| D09 | `_conditional` | If-Match ignored when If-None-Match is present | `test_conditional::test_evaluate_preconditions_follows_section_13_2_2[GET-"a"-"b"-"a"-412]` |
| D10 | `_conditional` | TRACE evaluates preconditions | `test_conditional::test_methods_without_a_representation_ignore_preconditions[TRACE]` |
| D11 | `_conditional` | method names case-insensitive | `test_conditional::test_evaluate_preconditions_follows_section_13_2_2[get-"a"-None-"a"-412]` |
| D12 | `_conditional` | empty list is a present field | `test_conditional::test_an_empty_list_of_field_lines_means_the_field_is_absent` |
| D13 | `_conditional` | a representation always exists | `test_conditional::test_if_match_is_false_without_a_representation` |
| D14 | `_conditional` | exists=False with a tag accepted | `test_conditional::test_exists_false_with_a_tag_is_rejected` |
| D15 | `_conditional` | exists skips the flag check | `test_contract_api::test_options_must_be_real_bools[<lambda>6-0]` |
| D16 | `_conditional` | bytes method accepted | `test_contract_api::test_the_method_must_be_text[GET]` |
| D17 | `_conditional` | HEAD gets 412 | `test_conditional::test_evaluate_preconditions_follows_section_13_2_2[HEAD-"a"-"a"-"a"-304]` |
| D18 | `_conditional` | ignored methods skip the header type check | `test_contract_api::test_a_header_of_another_type_raises_type_error[0]` |
| D19 | `_conditional` | If-Match wildcard ignores exists | `test_conditional::test_a_resource_can_exist_without_an_entity_tag` |
| D20 | `_conditional` | If-None-Match without a tag is false | `test_conditional::test_if_none_match_without_a_representation` |
| D21 | `_conditional` | falsy header counted as absent | `test_conditional::test_an_empty_list_of_field_lines_means_the_field_is_absent` |
| D22 | `_conditional` | If-None-Match strong current only | `test_properties::test_the_evaluators_are_the_comparisons_on_valid_fields[0]` |
| I01 | `__init__` | public names keep private modules | `test_contract_api::test_public_names_report_the_package_as_their_module[EntityTag]` |
70

Result: 65 killed on the first run. T15, P02 and P06 survived and are now killed by the
contracts marked "added" (each confirmed to fail on its mutant). T12 and R12 are
equivalent: `make_etag` and `parse_one` pass `weak` on to `format_etag`, which raises
the same `TypeError` with the same message.

## Packaging and e2e (items 8, 10, 13, 14), author run

`tests/test_e2e_wheel.py` (with `ETAG_E2E=1`) builds the wheel and sdist, installs the
wheel in a fresh venv, drives it from an empty folder and checks both archives: the
wheel holds the six modules and `py.typed` plus the licence; the sdist holds the
explicit list (sources, tests, the manifest and fixture, docs, LICENSE) and no fetched
file, report or scratch file. `tests/test_e2e_upgrade.py` (with `ETAG_E2E_PYPI=1`)
installs 0.2.0 from PyPI, probes 88,000 seeded calls, upgrades in place to the 1.0.0
wheel and gets identical results; the six listed changes differ exactly as documented.
Both passed on Elena's PC (CPython 3.14) and the laptop.

Supported Pythons: the 1.0.0 wheel installed into a fresh venv and the whole suite run
from a staging copy without `src` (imported from site-packages) on this PC: CPython
3.10.19, 3.11.5, 3.12.12, 3.13.2, 3.14.2 and 3.14.2 free-threaded, 343 passed and 8
skipped on each (the live oracles, the opt-in end-to-end modules, the mypy check).
CPython 3.8.20 and 3.9.25 refuse the wheel (`requires-python >=3.10`).

There is no command-line interface; the end-to-end test drives the installed package
from a separate process in an empty folder.

## Second pass verified (2026-10-19)

Gates and suite on a fresh clone of 47ed755 on Elena's PC, CPython 3.14, with the live
oracles installed (`.[oracle]`): `ruff format --check .`, `ruff check .` and
`mypy --strict src tests scripts` exit 0; `pytest` with `ETAG_E2E=1` and `ETAG_E2E_PYPI=1`
and a 300-second per-test timeout: 496 passed, none skipped.

Second author mutation round on the code changed by the second pass (`_plain`, the
single read of headers, the `EntityTag` field checks, the surrogate error, byte
subclasses), 22 mutations applied one at a time to a fresh clone of 47ed755 on Elena's
PC with the same runner as above, baseline green before and after:

| Id | Module | Mutation | Caught by |
| --- | --- | --- | --- |
| M01 | `_plain` | as_text accepts any object through str() | `test_contract_api::test_a_header_of_another_type_raises_type_error[header3]` |
| M02 | `_plain` | as_text keeps a subclass | `test_contract_hostile::test_text_subclasses_are_read_as_their_characters` |
| M03 | `_plain` | as_text judges by isinstance | `test_contract_types::test_a_value_claiming_another_type_gets_a_short_type_error[parse-str]` |
| M04 | `_plain` | as_octets returns a bytes subclass as is | `test_contract_hostile::test_bytes_subclasses_are_read_as_their_octets` |
| M05 | `_plain` | as_octets refuses bytearray subclasses | `test_contract_types::test_byte_subclasses_are_read_as_their_stored_octets[BufferArray]` |
| M06 | `_plain` | check_flag judges by isinstance | `test_contract_types::test_a_value_claiming_to_be_a_bool_is_refused[<lambda>0-True]` |
| M07 | `_plain` | check_flag accepts int by truth value | `test_contract_api::test_options_must_be_real_bools[<lambda>0-0]` |
| M08 | `_parse` | empty list of field lines read as an empty value | `test_conditional::test_an_empty_list_of_field_lines_means_the_field_is_absent` |
| M09 | `_parse` | a list of field lines iterated twice | `test_contract_types::test_field_lines_are_read_once_by_iterating_them[parse]` |
| M10 | `_parse` | an EntityTag accepted as a list of field lines | `test_contract_hostile::test_entity_tags_are_never_headers_and_always_have_two_fields` |
| M11 | `_parse` | parse_one skips the field count check | `test_contract_hostile::test_entity_tags_are_never_headers_and_always_have_two_fields` |
| M12 | `_parse` | parse_one reads an EntityTag through its attributes | `test_contract_hostile::test_entity_tag_subclasses_are_read_as_their_fields` |
| M13 | `_parse` | wildcard trims any whitespace | `test_oracle::test_random_fields_agree_with_the_grammar[0]` |
| M14 | `_compare` | matches reads the header a second time | `test_contract_types::test_field_lines_are_read_once_by_iterating_them[<lambda>0]` |
| M15 | `_conditional` | an empty list is a present, empty field | `test_conditional::test_an_empty_list_of_field_lines_means_the_field_is_absent` |
| M16 | `_conditional` | exists=False with a tag accepted | `test_conditional::test_exists_false_with_a_tag_is_rejected` |
| M17 | `_conditional` | method subclass read through its methods | `test_contract_hostile::test_a_method_subclass_cannot_pretend_to_be_get` |
| M18 | `_tag` | surrogate error index off by one | `test_contract_api::test_make_etag_hashes_any_contiguous_buffer` |
| M19 | `_tag` | surrogate re-raised as UnicodeEncodeError with the text | `test_contract_api::test_make_etag_hashes_any_contiguous_buffer` |
| M20 | `_tag` | make_etag reads a bytes subclass through its buffer | `test_contract_types::test_byte_subclasses_are_read_as_their_stored_octets[BufferBytes]` |
| M21 | `_tag` | make_etag encodes surrogates with surrogatepass | `test_contract_api::test_make_etag_hashes_any_contiguous_buffer` |
| M22 | `_compare` | matches tests the wildcard on the raw header | `test_compare::test_matches_reads_the_wildcard_in_every_header_form` (added) |

Result: 21 killed on the first run. M22 survived (only the bare `*` string was pinned
for `matches`); `test_matches_reads_the_wildcard_in_every_header_form` now pins padded,
byte and field-line forms and kills it (rerun on 4b60510). A first M14 that called an
unimported name was discarded as invalid and replaced by the version in the table.

Long fuzz on a fresh clone of 4b60510 on Elena's PC: the seeded property tests with 100,
100 and 150 extra seeds (300,000 evaluator checks, 300,000 precondition checks, 600,000
values through all thirteen fuzz calls), then 390,000 calls on raw random text and bytes
of up to 3,000 characters: no exception other than `ValueError` or `TypeError`, slowest
call 1.3 ms. Scaling of `parse`, `if_none_match` and `matches` on 100,000, 200,000 and
400,000 element fields: 0.35 s, 0.72 s, 1.54 s (linear).

Supported Pythons on this PC, the 4b60510 wheel installed into a fresh venv and the
suite run from a staging copy without `src`: CPython 3.10.19, 3.11.5, 3.12.12, 3.13.2,
3.14.2 and 3.14.2 free-threaded, 489 passed and 9 skipped on each (the live oracles,
the opt-in end-to-end modules, the mypy check); 3.8.20 and 3.9.25 refuse the wheel.
