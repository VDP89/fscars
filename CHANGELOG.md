# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Codex `PermissionRequest` deny surface.** `fscar init --adapter codex` now also registers the `PermissionRequest` hook — Codex's dedicated approval surface. A scar with `event_type = HookEventType.PERMISSION_REQUEST` (and optional `tool_matchers`) can deny the approval of a `Bash` / `apply_patch` / MCP request via the nested `decision: {"behavior": "deny", ...}` shape. It is deny-or-nothing: a non-blocking scar emits nothing, and fscars never returns `allow` (which would suppress the user's approval prompt). Adds `HookEventType.PERMISSION_REQUEST`.

### Planned

- Demo GIF rendered with VHS (`assets/demo.tape` storyboard ready in planning doc).
- Logo + brand assets.
- Homebrew tap.

## [0.6.0] — 2026-06-04

### Added

- **`fscar init --no-scars` and `fscar init --all`.** `--no-scars` wires the hook without copying any starter scars (for projects that manage their own, or CI). `--all` scaffolds the full packaged cookbook, including the advanced `import_aware_imports.py` omitted from the default set. The two flags are mutually exclusive.

### Fixed

- **The registry never registers a scar with an empty `scar_id`.** The fallback that instantiates `FunctionalScar` subclasses found in a module also instantiated base/template classes (e.g. `ImportAwareWriteScar`), whose `scar_id` is empty — so `fscar init --all` surfaced a blank, id-less row in `fscar list`. `_register_module_scars` now skips any scar (module-level or class-scanned) with a falsy `scar_id`.

## [0.5.0] — 2026-06-04

`fscar init` now scaffolds runnable starter scars, so a plain `pip install fscars` actually fires on first run. Until now the engine only discovered scars by importing the `cookbook` package — which the published **wheel did not ship** — so a pip-installed project loaded an empty registry and nothing ever fired. Scars are now **per-project**: copied into `.fscars/scars/`, editable, and loaded by file path at runtime.

### Added

- **`fscar init` scaffolds starter scars.** Init copies the five documented WARN-level starters (`large-write-review`, `utc-timestamps`, `csv-encoding`, `avoid-negative-framing`, `subagent-coverage-report`) plus `_template.py` into `.fscars/scars/`. Re-running init never overwrites files you have edited. The advanced `import_aware_imports` scar is intentionally not scaffolded (see `docs/cookbook_import_aware.md`).
- **`ScarRegistry.load_from_dir(scars_dir)`** — discovers scars from `*.py` files by file path (`importlib.util.spec_from_file_location`), so discovery no longer requires `cookbook` to be importable. Each module is registered in `sys.modules` under a path-unique name before execution, so a scar module that defines a module-level `@dataclass` loads correctly. Files prefixed with `_` (e.g. `_template.py`) and modules that fail to import are skipped without breaking the hook run.

### Changed

- **The hook entrypoint loads the project's own `.fscars/scars/`, not the global cookbook.** `run_hook` now builds the registry from the project root (resolved via the payload `cwd`), so scars are opt-in per project instead of every packaged cookbook scar firing globally wherever `cookbook` happened to be importable.
- **`engine.run()` with no registry now runs an empty one instead of `load_builtins()`.** Now that the wheel ships `cookbook`, defaulting to the catalog would let a bare `engine.run(payload)` surprise-fire global scars after `pip install`. Callers choose the registry explicitly: `load_from_dir` for a project, `load_builtins` for the shipped catalog.
- **`fscar list`** reflects the scars actually active in the project (`.fscars/scars/`) rather than the packaged catalog, and its empty-state message points to `fscar init`.
- **The `cookbook` package now ships in the wheel** (`[tool.hatch.build.targets.wheel] packages = ["fscars", "cookbook"]`). `fscar init` reads the starter sources from its packaged resources, and the `from cookbook.scars... import` examples in the docs now work after a plain `pip install`.

### Tests

- Added a deterministic test that `_force_utf8_io()` reconfigures both `sys.stdin` and `sys.stdout` from cp1252 to UTF-8, covering the input direction of the v0.4.1 fix (a payload with accented text in `tool_input` is read as UTF-8, not cp1252 mojibake) alongside the existing output-bytes test. Closes the coverage gap noted in the #8 review.

## [0.4.1] — 2026-06-03

### Fixed

- **Windows: hook stdout/stdin are now forced to UTF-8.** On a Windows console the default encoding is cp1252, so `run_hook` wrote a scar message containing a non-ASCII character (the em-dash in the `large-write-review` starter scar) as byte `0x97` instead of the UTF-8 sequence `e2 80 94`, producing output Codex and Claude Code cannot decode. `run_hook.main()` now reconfigures `sys.stdin`/`sys.stdout` to UTF-8 before reading the payload or writing the response. Affects both adapters on Windows. Found while verifying the v0.4.0 Codex adapter against a live Codex CLI (`codex-cli 0.136.0-alpha.2`) on Windows; covered by a raw-bytes regression test (the prior tests captured strings via `capsys` and missed the encoding entirely).

## [0.4.0] — 2026-06-03

Codex **native hooks** adapter — deterministic blocking on the Codex hook surfaces, lifting the long-standing roadmap item now that OpenAI ships a stable Codex hook API.

### Added

- **Codex native-hooks installer** — `fscar init --adapter codex` now registers the single fscars entrypoint as a native `command` hook in `.codex/hooks.json` for every parity event (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`), with a `commandWindows` override for Windows. On the surfaces Codex supports, `PreToolUse` can deny a `Bash` / `apply_patch` / MCP call before it runs (`hookSpecificOutput.permissionDecision: "deny"`). The `AGENTS.md` block is kept as an operational fallback and audit contract; the manifest (`.codex/fscars.json`) now reports `"mode": "native-hooks"`.
- **`fscar doctor --adapter codex`** — validates that `.codex/hooks.json` registers the fscars entrypoint for every parity event, that the manifest is in native-hooks mode, and that the `AGENTS.md` notes are present. `--adapter claude_code` remains the default.
- `apply_patch` payloads are normalized to the `Edit` tool with the first touched file path extracted, so existing Write/Edit-scoped cookbook scars fire on Codex file edits.

### Changed

- `Adapter.emit_output(output)` → `Adapter.emit_output(output, payload=None)`. The Codex adapter uses the originating event to pick its response shape (`permissionDecision` on `PreToolUse`, `decision: "block"` + top-level `reason` as feedback elsewhere, `additionalContext` otherwise) and echoes `hookEventName`. The Claude Code adapter accepts the argument and is behavior-unchanged; `run_hook` passes the payload through.

### Fixed

- `fscar dashboard --brand` now fails with a clear error message instead of an unhandled exception when the palette file is unreadable, not UTF-8, not valid JSON, or not a JSON object (catches the three orthogonal file/JSON error branches plus a shape check).

### Tests

- Added an end-to-end `fscar audit --classifiers MODULE:FUNC` test (Capa 4 runs over real opportunities, not the no-op path) plus two `--brand` rejection tests for the defensive validation.
- New Codex coverage: official `Bash` / `apply_patch` / MCP payload parsing, per-event emit (deny vs feedback vs context), native `hooks.json` registration + idempotency + foreign-hook preservation across install/uninstall, `doctor --adapter codex`, and a `run_hook --adapter codex` end-to-end over an `apply_patch` write.

### Acknowledgments

- OpenAI for the [Codex hooks API](https://developers.openai.com/codex/hooks), which lifted this from a roadmap item to a shipped adapter.

### Known limitations

- Codex `PreToolUse` is a guardrail, not a complete boundary: it does not intercept every shell path yet, and WebSearch / other non-shell, non-MCP tools are not intercepted. Non-managed command hooks must be trusted once via `/hooks` in the Codex CLI before they run. fscars registers a catch-all hook (no `matcher`) per event and lets the engine filter per scar.

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
