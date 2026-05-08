# Cookbook — starter scars

Each module here exports a module-level `scar` instance. The default
registry discovers them automatically when you call
`ScarRegistry.load_builtins()`.

## How to read a scar

| Attribute | Meaning |
|---|---|
| `scar_id` | Stable slug, kebab-case. Goes in `fires.jsonl`. |
| `name` | Human-readable label shown in `fscar list`. |
| `rule` | The binary rule, the way you would explain it to a teammate. |
| `severity` | `warn` (inject context) or `block` (deny tool call). |
| `event_type` | When the hook fires: `PreToolUse`, `UserPromptSubmit`, etc. |
| `tool_matchers` | Tool names this scar applies to (Pre/Post tool only). |
| `enabled` | Set `False` to ship the scar disabled by default. |

## Available starters

| File | What it does |
|---|---|
| `large_write_review.py` | Reminds the operator to self-review code writes over 200 lines. |
| `utc_timestamps.py` | Pushes back on `time.Now()` / `new Date()` in handler-style files. |
| `csv_encoding.py` | Requires explicit `encoding="utf-8"` in `pandas.read_csv` calls. |
| `avoid_negative_framing.py` | Blocks "we don't do X" patterns in marketing copy. |
| `subagent_coverage_report.py` | Reminds the operator to ask subagents for a coverage report. |
| `_template.py` | Copy-paste starting point. |

## Adding a new scar

1. Copy `_template.py` to `<your_slug>.py`.
2. Set the metadata fields, implement `matches` and `build_output`.
3. Export `scar = YourScar()` at the bottom of the module.
4. Add a test under `tests/cookbook/test_<your_slug>.py`.

The registry discovers your scar automatically — no central registration
file to update.

## Five-invariant checklist before shipping

The companion paper identifies five invariants that distinguish corrections
that persist from those that decay. Use them as a sanity check:

- [ ] **Binary rule** — expressible as a concrete check, not a judgment call.
- [ ] **Durable physical support** — the rule lives in a file the model reads every session.
- [ ] **Structural integration** — the rule is wired into the output format, not appended.
- [ ] **Non-passive technical trigger** — the hook fires at the moment of risk.
- [ ] **Refinable activation metric** — fires are logged, recall can be computed.
