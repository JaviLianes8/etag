# Contributing

Thanks for taking the time. This project keeps a small, predictable shape.

## Setup

```
pip install -r requirements-dev.txt
```

## Before you open a pull request

- Keep public API in `src/etag/__init__.py`; internals live in `_`-prefixed modules.
- Add a test for the behaviour you change. The suite needs no network: the reference
  checks read the files `python scripts/fetch_upstream.py` fetches and skip without them,
  and the end-to-end tests that build the wheel and install from PyPI run only with
  `ETAG_E2E=1` and `ETAG_E2E_PYPI=1`.
- Run `scripts/check.ps1` (format, lint, types, tests) and make sure it passes.
- One logical change per commit, imperative subject line.

Open an issue first if the change is large or shifts the public API.
