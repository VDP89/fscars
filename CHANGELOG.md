# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- Demo GIF rendered with VHS (`assets/demo.tape` storyboard ready in planning doc).
- Logo + brand assets.
- PyPI publication of v0.1.0.
- Homebrew tap.
- Codex CLI adapter once upstream hook API stabilises.

## [0.1.0] — 2026-05-08

Initial alpha. Bootstrapped during a single session at DG Ingenieria SRL.

### Added

- Core package: `payload`, `scar`, `fire`, `log`, `engine`, `store` (Pydantic v2 models).
- Single hook entrypoint: `python -m fscars.run_hook` — replaces per-scar hook scripts.
- Claude Code adapter: parses Claude Code stdin, emits `hookSpecificOutput`,
  installs / uninstalls `.claude/settings.json` entries idempotently.
- CLI (Typer): `init`, `list`, `log`, `stats`, `disable`, `doctor`.
- Cookbook with 5 starter scars (sanitized abstractions of patterns from the
  Lucy Syndrome production case):
  - `large-write-review`
  - `utc-timestamps`
  - `csv-encoding`
  - `avoid-negative-framing`
  - `subagent-coverage-report`
- Pytest test suite covering payload, scar base, log, engine dispatch,
  Claude Code adapter, run_hook entrypoint, and all 5 cookbook scars.
- Apache 2.0 license + README + CHANGELOG + CONTRIBUTING + BRAND.
- GitHub Actions CI workflow (lint + tests on Linux/macOS/Windows × Py 3.10–3.12).

### Notes

- Versioned schema for `fires.jsonl` (`schema_version: 1`) so future readers
  can migrate older entries deterministically.
- Logging is silent on failure by design: a logging error must never break
  the host harness.
- Engine swallows scar exceptions for the same reason — a buggy scar in the
  registry does not crash the dispatch.

[Unreleased]: https://github.com/Vdp89/fscars/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Vdp89/fscars/releases/tag/v0.1.0
