<!-- markdownlint-disable MD033 -->
<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/fscars-logo-dark.svg">
    <img src="assets/fscars-logo.svg" alt="Functional Scars" width="360" style="max-width: 100%; height: auto;">
  </picture>
  <p><strong>Stop explaining the same fix every session. Make corrections persist.</strong></p>

  <p>
    <a href="https://github.com/Vdp89/fscars/actions/workflows/ci.yml">
      <img alt="CI" src="https://img.shields.io/badge/CI-pending-lightgrey">
    </a>
    <a href="LICENSE">
      <img alt="License" src="https://img.shields.io/badge/License-Apache%202.0-blue.svg">
    </a>
    <a href="https://claude.com/claude-code">
      <img alt="Claude Code" src="https://img.shields.io/badge/Claude%20Code-Compatible-6366f1">
    </a>
    <a href="https://doi.org/10.5281/zenodo.19555971">
      <img alt="Companion paper" src="https://img.shields.io/badge/Paper-Lucy%20Syndrome-orange">
    </a>
  </p>
</div>

> Status: **alpha (v0.1.0)**. Core engine, Claude Code adapter, and 5 starter scars are working. Demo GIF, PyPI release, and Codex adapter are on the roadmap. Read [CHANGELOG.md](CHANGELOG.md) for the current state.

---

## What is a Functional Scar?

A **scar** is what an operator's correction becomes when you make it deterministic. Not text presented to the model — code that runs outside the model, intercepts the moment of risk, and pushes back.

|  | System prompt | Memory / KB | Hook | Functional Scar |
| --- | --- | --- | --- | --- |
| Where does the rule live? | In context | In context | In code outside the model | In code outside the model |
| Does the model decide whether it applies? | Yes | Yes | No | No |
| Does it survive `/compact`? | Partial | Yes | Yes | Yes |
| Does it learn from its own fires? | No | No | Manual | **Yes** |
| Built directly from a real correction? | No | No | Manual | **Yes — by design** |

Functional Scars complement memory and skills, they do not compete with them. The companion paper [*Lucy Syndrome in LLM Agents*](https://doi.org/10.5281/zenodo.19555971) explains the underlying framework — five invariants that distinguish corrections that persist from those that decay.

This repository is the first installable implementation of those invariants.

---

## Quick start

```bash
pip install fscars            # PyPI release pending — for now: pip install -e .
cd your-project
fscar init                    # creates .fscars/ + wires Claude Code
fscar list                    # 5 starter scars come pre-installed
```

Three quick wins to try right away:

```bash
# 1) Web dev — kill timezone regressions in handler code
fscar list | grep utc-timestamps

# 2) Data science — require explicit UTF-8 in pandas.read_csv
fscar list | grep csv-encoding

# 3) Marketing copy — block "we don't do X" framing
fscar list | grep avoid-negative-framing
```

Once installed, every Claude Code tool call passes through the engine. When a scar matches, the engine emits an `additionalContext` reminder (or blocks the call when the scar is severity `block`) and writes one JSON line to `.fscars/logs/fires.jsonl`.

---

## Commands

| Command | Description |
| --- | --- |
| `fscar init` | Initialize `.fscars/` and register the hook entrypoint |
| `fscar list` | Show registered scars + fire counts |
| `fscar log [-n N]` | Show the most recent fires (filter by `--scar`, `--session`) |
| `fscar stats` | Compute fire counts, latency p50/p99, tokens added |
| `fscar disable <scar_id>` | Disable without deleting (use `--enable` to restore) |
| `fscar doctor` | Diagnose installation and hook wiring |
| `fscar --version` | Print the installed version |

The hook entrypoint is `python -m fscars.run_hook`. Single command across every event type — no per-scar hook scripts.

---

## How it works

```
┌─────────────────────────────────────────────────────────────┐
│                          fscars.core                        │
│   payload · scar · engine · log · store · fire (Pydantic)   │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │  fscars.adapters/           │
        │   claude_code (v0.1)        │
        │   codex (roadmap)           │
        │   cursor (community)        │
        └──────────────┬──────────────┘
                       │
                       ▼
       .claude/settings.json wired with one entrypoint:
              python -m fscars.run_hook
```

The engine reads stdin, parses through the right adapter, dispatches to every matching scar, and emits the combined `additionalContext` plus exit code. A failure inside any scar is swallowed — the host harness must never crash because of fscars.

---

## Cookbook

`cookbook/scars/` ships starter scars you can use directly or copy-paste:

| File | What it does |
| --- | --- |
| `large_write_review.py` | Reminds the operator to self-review writes over 200 lines |
| `utc_timestamps.py` | Pushes back on `time.Now()` / `new Date()` in handler files |
| `csv_encoding.py` | Requires explicit `encoding="utf-8"` in `pandas.read_csv` |
| `avoid_negative_framing.py` | Blocks "we don't do X" patterns in marketing copy |
| `subagent_coverage_report.py` | Reminds the operator to ask subagents for a coverage report |
| `_template.py` | Copy-paste starting point for new scars |

See [`cookbook/scars/README.md`](cookbook/scars/README.md) for the contract and the 5-invariant checklist.

---

## When NOT to use fscars

A scar only works when the correction satisfies the five invariants. If your fix is:

- **Subjective** ("I prefer tabs over spaces") — use `.editorconfig` or a linter.
- **Proportional** ("use async when it makes sense") — leave it to the model's judgment.
- **One-off** (the case has not repeated) — wait for the second occurrence first.
- **Non-binary** (cannot be checked deterministically) — keep it in your knowledge base.

These are the four cases the paper explicitly excludes. Adding a scar there creates noise without preventing anything.

---

## Platforms

Currently supported:

- **Claude Code** (Anthropic) — full adapter, all event types

On the roadmap:

- **Codex CLI** (OpenAI) — the adapter API is public, awaiting hook stability upstream
- **Cursor**, **Aider**, **Continue.dev** — community adapters welcome

The core engine is platform-agnostic. Each adapter is a small glue layer (~300 LoC) that translates between platform-specific JSON shapes and the canonical `HookPayload`.

---

## The research behind this

Functional Scars is the reference implementation of the framework described in [*Lucy Syndrome in LLM Agents: A Practitioner Framework for Cross-Session Correction Persistence*](https://doi.org/10.5281/zenodo.19555971) (Del Puerto, 2026). The paper analyzes 163 findings from 17 production session logs, identifies 5 persistence invariants, and proposes a 3-layer implementation model.

If you want the why, read the paper. If you want the how, you are in the right place.

The first derivative essay [*From Memory to Scar*](https://victordelpuerto.com/posts/from-memory-to-scar/) (May 2026) extends the four-layer progression with Anthropic's Managed Agents Memory beta as a working example of Layer 3 industrialized.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). New adapters and cookbook scars are especially welcome.

```bash
git clone https://github.com/Vdp89/fscars
cd fscars
pip install -e ".[dev]"
pytest -q
ruff check fscars cookbook tests
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

<div align="center">
  <sub>
    Built on research first published as <a href="https://doi.org/10.5281/zenodo.19555971">Lucy Syndrome in LLM Agents</a> ·
    <a href="https://github.com/Vdp89/lucy-syndrome">companion repo</a>
  </sub>
</div>
