<!-- markdownlint-disable MD033 -->
<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/fscars-launch-dark.gif">
    <img src="assets/fscars-launch.gif" alt="Functional Scars" width="600" style="max-width: 100%; height: auto;">
  </picture>
  <p><strong>Stop explaining the same fix every session. Make corrections persist.</strong></p>

  <p>
    <a href="https://github.com/VDP89/fscars/actions/workflows/ci.yml">
      <img alt="CI" src="https://github.com/VDP89/fscars/actions/workflows/ci.yml/badge.svg">
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

> Status: **alpha**. `pip install fscars` is live on PyPI (v0.2.0). Core engine, Claude Code adapter, 5 starter scars, and the validation layers (`fscars.validation`) — a three-tier loop for turning observations into auditable outcomes — ship in that release; the Codex instruction-mode installer is merged on `main` and lands in the next release. Native Codex hook blocking remains on the roadmap. Read [CHANGELOG.md](CHANGELOG.md) for the current state.

---

## Why this exists

A junior engineer reads the textbooks and learns the fundamentals — that is the floor. What turns the junior into a senior is the weight that mistakes leave behind: the migration that ran half-applied in production, the timezone bug that shipped to a customer, the build that broke at 2am. Those scars become heavier than any chapter of the book; they bend future decisions in a way pure knowledge cannot.

AI coding agents come into your project with a strong prior — billions of tokens of training, especially on code. But the way *your* assistant behaves on *your* codebase is not just that prior; it is shaped by every correction you make along the way. The catch is that those corrections rarely survive: the next session starts from training again, and the model regresses to its statistical default in any area where the correction carries less weight than the prior. A functional scar is the anchor that gives your correction enough weight to bend the next decision.

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
pip install fscars            # v0.2.0 on PyPI
# the Codex adapter below is on main until the next release: pip install -e .
cd your-project
fscar init                    # creates .fscars/ + wires Claude Code
fscar init --adapter codex    # creates .fscars/ + writes Codex AGENTS.md guidance
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
| `fscar validate` | Run Capa 4 deterministic rules over observed opportunities |
| `fscar dashboard` | Render markdown + HTML metrics from fires + opportunities |
| `fscar audit` | Validate + cross-link fires↔opportunities + render dashboard |
| `fscar --version` | Print the installed version |

The hook entrypoint is `python -m fscars.run_hook`. Single command across every event type — no per-scar hook scripts. For Codex today, `fscar init --adapter codex` installs instruction-mode support in `AGENTS.md` plus `.codex/fscars.json`; native pre-tool blocking is reserved until Codex exposes a stable hook API.

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
        │   codex (instruction mode)  │
        │   cursor (community)        │
        └──────────────┬──────────────┘
                       │
                       ▼
       .claude/settings.json wired with one entrypoint:
              python -m fscars.run_hook

       Codex projects get AGENTS.md + .codex/fscars.json
       until native hook registration is stable upstream
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
| `import_aware_imports.py` | AST-based detection of writes that import a watched package — see [cookbook_import_aware.md](docs/cookbook_import_aware.md) |
| `_template.py` | Copy-paste starting point for new scars |

See [`cookbook/scars/README.md`](cookbook/scars/README.md) for the contract and the 5-invariant checklist.

---

## Validation layers

Once you have observation in place, the next problem is precision: out of every hundred fires, how many actually prevented an error? `fscars.validation` is a three-tier loop developed in production during May 2026 that downgrades the labelling problem from "operator stares at thousands of rows" to "operator confirms an edge slice automation cannot resolve":

1. **Capa 4** — deterministic rules per scar. Free, predictable, resolves most clearly-true and clearly-false opportunities.
2. **Capa 3** — LLM classifier (subprocess to the local `claude` CLI) for what Capa 4 leaves ambiguous. Configurable threshold, parallel workers.
3. **Capa 5** — cross-link the observed opportunities to actual hook fires so coverage stops being a proxy.

A `fscars.dashboard` module renders the resulting metrics as markdown + self-contained HTML; `fscars.io.safe_jsonl` guards concurrent pipeline writes with file-locked atomic merges.

The CLI shortcut for the common case:

```bash
fscar audit --classifiers myapp.scars:register --period 30d
```

Full architecture, examples, and the cross-link / outcome marker details: [docs/advanced_validation.md](docs/advanced_validation.md).

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
- **Codex CLI** (OpenAI) — instruction-mode installer via `AGENTS.md` + `.codex/fscars.json`; see [docs/codex_integration_plan.md](docs/codex_integration_plan.md)

On the roadmap:

- **Codex native hooks** — deterministic pre-tool blocking once Codex hook stability is available upstream
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
