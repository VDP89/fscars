# Codex integration plan

Status: **implemented as instruction-mode installer; native hook mode remains a roadmap item**.

This document captures the concrete, test-backed plan for transferring
Functional Scars to OpenAI Codex without overstating the current Codex surface.
OpenAI positions Codex as a coding agent for software development that can work
across real codebases, and the OpenAI developer site lists production workflows
such as code review, repository analysis, repeatable skills, CLI workflows, and
documentation upkeep. That is enough to make `fscars` useful in Codex today as a
project instruction + audit loop, while the deterministic pre-tool blocking mode
waits for a stable native Codex hook API.

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
| `install(project_root)` | Writes an idempotent `AGENTS.md` block plus `.codex/fscars.json`. |
| `uninstall(project_root)` | Removes only the fscars block and manifest. |
| `parse_stdin(raw)` | Parses a normalized/future-wrapper JSON payload into `HookPayload`. |
| `emit_output(output)` | Emits generic JSON for a future Codex hook/wrapper contract. |

The installer uses **instruction mode** because the repository does not rely on
an undocumented native Codex pre-tool hook. The reserved command is still
recorded for the future:

```bash
python -m fscars.run_hook --adapter codex
```

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

## Future native hook milestone

When Codex exposes a stable hook/event contract, the native milestone is small:

1. map Codex event names to `HookEventType` in `CodexAdapter.parse_stdin`;
2. update `CodexAdapter.emit_output` to the exact Codex hook response schema;
3. change `install()` from instruction-only to hook registration plus the
   `AGENTS.md` operating notes;
4. add fixture tests for real Codex payloads;
5. update this document and remove the roadmap caveat from README.

The core value of the current design is that these steps do **not** require
rewriting `FunctionalScar`, `HookPayload`, the engine, logs, validation layers,
or cookbook scars.
