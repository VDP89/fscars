# Codex integration plan

Status: **native hooks shipped in v0.4.0** (deterministic `PreToolUse` blocking on
the surfaces Codex supports); the `AGENTS.md` instruction block is retained as an
operational fallback and audit contract. A second deny surface,
**`PermissionRequest`**, was added on top — a scar can deny the approval of a
`Bash` / `apply_patch` / MCP request.

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
| `emit_output(output, payload)` | Emits the Codex response schema: nested `decision: {"behavior": "deny", ...}` on `PermissionRequest` block (silent otherwise — never `allow`), `permissionDecision: "deny"` on `PreToolUse` block, `decision: "block"` feedback elsewhere, `additionalContext` otherwise, echoing `hookEventName`. |

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
- point at the native hook entrypoint registered in `.codex/hooks.json` as the
  primary enforcement surface.

This makes Codex treat scars as an operational contract, not a vague memory, and
keeps a usable fallback for surfaces the native hook layer does not cover.

## Release process (followed for v0.4.0)

1. Implement the adapter, tests, README, changelog, and this plan on a branch.
2. Gate locally and in CI (macOS / Linux / Windows × Py 3.10–3.12):

   ```bash
   pytest -q
   ruff check fscars cookbook tests
   mypy fscars
   ```

3. Open a PR with a title that states the support level (`feat(codex): native
   hooks adapter`), and have it reviewed out-of-band (Codex reviewed #7).
4. Squash-merge, tag `v*.*.*`, and let `release.yml` publish to PyPI via the
   OIDC trusted publisher behind the `pypi` environment's required-reviewer gate.

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

## PermissionRequest deny surface (added post-v0.4.0)

`PermissionRequest` is Codex's dedicated approval surface. The official contract
returns a **nested** decision object — distinct from `PreToolUse`:

```json
{"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                        "decision": {"behavior": "deny", "message": "..."}}}
```

Codex resolves multiple hooks as "any `deny` wins; an `allow` lets the request
proceed without surfacing the approval prompt." fscars therefore treats this as a
**deny-or-nothing** surface: a blocking scar emits `behavior: "deny"`, and a
non-blocking scar emits nothing (`{}`). fscars never returns `allow` — auto
-approving a request the user would otherwise see is not a scar's call to make. A
scar opts in by setting `event_type = HookEventType.PERMISSION_REQUEST`;
`tool_matchers` filter by `tool_name` just like `PreToolUse`. Two surface-specific
details (confirmed in the PR #12 review against the doc):

- **Exit code 0.** The deny travels through the JSON decision object only; the
  doc does not list exit code 2 as a decision path for `PermissionRequest`, so
  `run_hook` returns 0 here (unlike `PreToolUse`/`Stop`, where exit 2 also blocks).
- **Canonical `apply_patch`.** For the tool-use events, `apply_patch` is bridged
  to `Edit` so the cross-platform cookbook scars fire. On `PermissionRequest` —
  a Codex-specific surface — the canonical `apply_patch` name is preserved, so a
  scar uses `tool_matchers = ("apply_patch",)`.

## Resolved verification item — catch-all matcher

fscars registers each event hook **without** a `matcher` (catch-all), relying on
the engine to filter per scar. Confirmed valid in the PR #7 out-of-band review
against the official doc: `"*"`, `""`, or an omitted `matcher` all mean match-all.
No change needed.
