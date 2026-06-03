# Codex integration plan

Status: **native hooks shipped in v0.4.0** (deterministic `PreToolUse` blocking on
the surfaces Codex supports); the `AGENTS.md` instruction block is retained as an
operational fallback and audit contract.

This document captures the concrete, test-backed integration for transferring
Functional Scars to OpenAI Codex. OpenAI now ships a stable Codex hook API
([developers.openai.com/codex/hooks](https://developers.openai.com/codex/hooks))
with the same matcher-group shape Claude Code uses, so `fscars` registers a single
native `command` hook in `.codex/hooks.json` for every parity event. On
`PreToolUse`, a scar can deny a `Bash` / `apply_patch` / MCP call before it runs.
The instruction + audit loop in `AGENTS.md` remains as a fallback for surfaces the
hook layer does not yet cover.

## Goal

Ship an installer that a maintainer can run in a repository:

```bash
fscar init --adapter codex
```

The installer must:

1. create the normal `.fscars/` store;
2. add an idempotent `AGENTS.md` block that tells Codex how to apply scars;
3. write `.codex/fscars.json` so GitHub reviewers and future tooling can detect
   the Codex integration state;
4. leave the core engine and existing scars unchanged;
5. be covered by unit and CLI smoke tests.

## Current implementation

`fscars.adapters.codex.CodexAdapter` provides the same interface as the Claude
Code adapter:

| Method | Current Codex behavior |
| --- | --- |
| `install(project_root)` | Registers the fscars entrypoint as a native `command` hook in `.codex/hooks.json` (idempotent, preserves foreign hooks), writes the `AGENTS.md` fallback block, and a `.codex/fscars.json` manifest in `"mode": "native-hooks"`. |
| `uninstall(project_root)` | Removes only the fscars handlers from `.codex/hooks.json`, plus the `AGENTS.md` block and manifest. |
| `parse_stdin(raw)` | Parses the Codex hook payload into `HookPayload`; `apply_patch` is normalized to `Edit` with the first touched file path extracted. |
| `emit_output(output, payload)` | Emits the Codex response schema: `permissionDecision: "deny"` on `PreToolUse` block, `decision: "block"` feedback elsewhere, `additionalContext` otherwise, echoing `hookEventName`. |

The installer registers a catch-all native hook (no `matcher`) per parity event,
routing every tool to the single entrypoint, which then filters per scar:

```bash
python -m fscars.run_hook --adapter codex
```

Codex requires non-managed command hooks to be trusted once via `/hooks` in the
CLI before they run.

## What Codex receives in `AGENTS.md`

The generated block tells Codex to:

- run `fscar audit --period 30d` before final delivery when `.fscars/` exists;
- inspect `.fscars/logs/fires.jsonl` and `.fscars/logs/opportunities.jsonl`
  when a task touches scar-sensitive files;
- propose or add new cookbook scars when a repeated binary correction appears;
- either fix a scar warning or explicitly explain why it is a false positive;
- keep the native hook command reserved for future hook support.

This makes Codex treat scars as an operational contract, not a vague memory.

## GitHub rollout checklist

1. Commit the adapter, tests, README, changelog, and this plan.
2. Open a PR with a title that makes the support level explicit, for example:
   `Add Codex instruction-mode installer`.
3. In the PR body, state that native hook blocking is **not** claimed yet.
4. Run:

   ```bash
   pytest -q
   ruff check fscars cookbook tests
   mypy fscars
   ```

5. After merge, update release notes with:
   - new `fscar init --adapter codex` command;
   - generated `AGENTS.md` contract;
   - `.codex/fscars.json` manifest;
   - limitation: instruction/audit mode until Codex exposes a stable hook API;
   - type-check status: `mypy fscars` passes under strict mode.

## Native hook milestone — shipped in v0.4.0

All five steps are done, and — as designed — none required rewriting
`FunctionalScar`, `HookPayload`, the engine, logs, validation layers, or the
cookbook scars:

1. Codex event names map to `HookEventType` in `CodexAdapter.parse_stdin`.
2. `CodexAdapter.emit_output(output, payload)` emits the exact Codex response
   schema (`permissionDecision` / `decision` / `additionalContext`).
3. `install()` registers a native `command` hook in `.codex/hooks.json` and keeps
   the `AGENTS.md` operating notes as a fallback.
4. Unit + CLI + end-to-end tests cover real Codex payloads (`Bash`, `apply_patch`,
   MCP), per-event emit, idempotent install, foreign-hook preservation, and
   `run_hook --adapter codex`.
5. This document and the README reflect the shipped state.

The single contract change was widening `Adapter.emit_output` to take the
originating `payload` (optional, default `None`), so Codex can pick a per-event
response shape. The Claude Code adapter is behavior-unchanged.

## Open verification item

fscars registers each event hook **without** a `matcher` (catch-all), relying on
the engine to filter per scar. If a future Codex parser requires an explicit
`matcher` for catch-all groups, set `"matcher": ""` in `CodexAdapter._merge_fscars_hooks`.
This is the one assumption to confirm against a live Codex CLI.
