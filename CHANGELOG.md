# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `fscar dashboard --brand` now fails with a clear error message instead of an unhandled exception when the palette file is unreadable, not UTF-8, not valid JSON, or not a JSON object (catches the three orthogonal file/JSON error branches plus a shape check).

### Tests

- Added an end-to-end `fscar audit --classifiers MODULE:FUNC` test (Capa 4 runs over real opportunities, not the no-op path) plus two `--brand` rejection tests for the new defensive validation.

### Planned

- Demo GIF rendered with VHS (`assets/demo.tape` storyboard ready in planning doc).
- Logo + brand assets.
- Homebrew tap.
- Codex native hook mode once upstream hook API stabilises.

## [0.3.0] — 2026-06-02

Codex instruction-mode adapter + cross-platform install coverage.

### Added

- **Codex instruction-mode installer** — `fscar init --adapter codex` now writes an idempotent `AGENTS.md` block plus `.codex/fscars.json`, registers the `codex` run-hook adapter name, and documents the tested rollout plan in `docs/codex_integration_plan.md`. Native Codex pre-tool blocking remains a roadmap item until a stable hook API is available.

### Fixed

- `mypy fscars` now passes under the repository strict configuration by adding explicit JSON-row types across the validation, dashboard, IO, adapter, and hook-entrypoint modules.
- `fscar init` no longer mangles its "wired hook entry" message on Windows. The relative descriptor was run through `pathlib` (`project_root / wired`), which rewrote the `/` in `.codex/fscars.json` to `\` and broke `test_init_codex_wires_agents_and_manifest` on every Windows CI job (macOS and Linux passed because their separator is already `/`); the descriptor is now echoed verbatim.

### Tests

- Added `tests/cli/test_init_claude_code.py` so the default `claude_code` install path is exercised end-to-end through the CLI across the macOS / Linux / Windows matrix, matching the existing Codex coverage and guarding against the path-separator regression on every adapter.

### Acknowledgments

- The Codex instruction-mode adapter (`fscars/adapters/codex/`, [#6](https://github.com/VDP89/fscars/pull/6)) was designed and implemented by **OpenAI Codex**, which mapped out and built its own integration path into fscars — the `AGENTS.md` install block, the `.codex/fscars.json` manifest, and the rollout plan in `docs/codex_integration_plan.md`. fscars is built and maintained at **[DG Ingeniería SRL](https://dgingenieriasrl.com)** by **[Victor Del Puerto](https://victordelpuerto.com)**. See [CONTRIBUTORS.md](CONTRIBUTORS.md).

## [0.2.0] — 2026-05-26

Validation layers + dashboard + CLI pipeline. Spun out of seven weeks of
production operation at DG Ingenieria SRL.

### Added

- **`fscars.validation`** — three-tier loop for turning observed
  opportunities into auditable outcomes:
  - **Capa 4** (`fscars.validation.rules`) — deterministic per-scar rules
    classifier with `RulesEngine`, `apply_decisions`, `summarize`, and a
    reference `line_count_classifier` to copy-paste against.
  - **Capa 3** (`fscars.validation.llm`) — `LLMClassifier` that shells out
    to the local `claude` CLI via `subprocess.run` with UTF-8 + replace
    error handling and `shutil.which` shim resolution (Windows-safe);
    configurable model, confidence threshold, prompt template, and
    `ThreadPoolExecutor` workers. `apply_verdict` writes the decision back
    to the opportunity row, gating on threshold.
  - **Capa 5** (`fscars.validation.cross_link`) — `cross_link_fires_opps`
    pairs observed opportunities with actual fires by `(scar_id,
    session_id, timestamp window, filename)`; `real_coverage` reports
    matched / missed / coverage per scar.
  - **Outcome marker** (`fscars.validation.outcome`) — `OutcomeMarker`
    classifies and applies retroactive fire outcomes
    (`error_prevented`, `false_positive`, `error_repeated`,
    `error_despite_fire`, `unknown`), with a `mark_manually` path that
    flags rows as human-reviewed.
- **`fscars.io.safe_jsonl.safe_save_jsonl`** — file-locked atomic JSONL
  writes with field-level merge by `event_id` for concurrent pipeline
  safety. Stale locks (>120s) are auto-broken so a crashed writer cannot
  deadlock the pipeline.
- **`fscars.dashboard`** — markdown + self-contained HTML metrics
  dashboard with parametric `BRAND_COLORS` palette (`DEFAULT_BRAND` ships
  a neutral slate/blue scheme), period filtering (`all / 7d / 30d / 90d`),
  per-scar table, health flags, and LLM-cost estimation.
- **`fscars.core.opp_log`** — `read_opps`, `save_opps`, `log_opportunity`
  helpers that mirror `fscars.core.log`. `StoreLayout` now exposes
  `opps_file` at `.fscars/logs/opportunities.jsonl`.
- **CLI commands**: `fscar validate` runs Capa 4 over opportunities (with
  optional `--classifiers MODULE:FUNC` extension point); `fscar
  dashboard` renders the metrics summary; `fscar audit` chains
  validate → cross-link → dashboard end to end.
- **Cookbook**: `cookbook/scars/import_aware_imports.py` — AST-based
  detection of edits that actually import a watched package, plus a
  disabled example (`DocxImportReminderScar`) showing the pipeline-path +
  usage-hint escape hatch. Generalised from the production fix to a v1
  hook that had a 100% false-positive rate.

### Changed

- `README.md` — new "Validation layers" section and updated command table.
- `pyproject.toml` — version bumped 0.1.0 → 0.2.0.

### Tests

- 96 new tests covering `io.safe_jsonl`, every `validation` submodule, the
  dashboard renderer, opportunity log, CLI smoke tests for the three new
  commands (with a regression for `FireRecord.event_id` UUID JSON
  serialisation), and the import-aware cookbook scar. Coverage on the new
  modules: 90% global, 79%+ per module.

### Acknowledgments

The validation layer architecture in this release was developed and
validated in production at **[DG Ingenieria SRL](https://dgingenieriasrl.com)**
([Victor Del Puerto](https://victordelpuerto.com)) during May 2026: seven
weeks of operation across 915 fires and 3,785 captured opportunities, with
five bugs of instrumentation caught and patched along the way. The runtime
that produced the data set lives in the DG operator workspace; only the
domain-neutral abstractions (the engine, IO, classifier shapes, dashboard
renderer, and AST-aware hook template) are released here, free of any
project-specific paths or content.

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

[Unreleased]: https://github.com/Vdp89/fscars/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Vdp89/fscars/releases/tag/v0.2.0
[0.1.0]: https://github.com/Vdp89/fscars/releases/tag/v0.1.0
