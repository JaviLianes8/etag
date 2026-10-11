# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

- `make_etag` builds a quoted, optionally weak entity-tag from bytes or text.
- `parse` reads an ETag or If-None-Match / If-Match header into `(value, weak)` pairs,
  handling the wildcard and rejecting malformed input.
- `matches` applies the RFC 7232 weak and strong comparison rules for conditional
  requests.
