# Validation layers — turning observations into auditable outcomes

A hook fires. Did it fire because the target error was about to happen, or
because the heuristic is noisy? Without a way to label fires after the fact,
you cannot compute precision or recall — and that means you cannot tell
whether a scar is paying for itself.

`fscars.validation` is the three-tier loop developed in production at DG
Ingenieria SRL (May 2026, seven weeks of operation). It downgrades the
labelling problem from "operator stares at thousands of rows" to "operator
confirms a small edge slice that automation can't resolve".

```
┌──────────────────────────────────────────────────────────────────────┐
│  observer captures opportunity ──┐                                   │
│  (.fscars/logs/opportunities.jsonl)                                  │
│                                  │                                   │
│                                  ▼                                   │
│                          ┌───────────────┐                           │
│                          │  Capa 4       │  fscars.validation.rules  │
│                          │  rules engine │  deterministic, free      │
│                          └───────┬───────┘                           │
│                                  │                                   │
│                       auto_tp ◀──┼──▶ auto_fp                        │
│                                  │                                   │
│                                  ▼                                   │
│                              ambiguous                               │
│                                  │                                   │
│                                  ▼                                   │
│                          ┌───────────────┐                           │
│                          │  Capa 3       │  fscars.validation.llm    │
│                          │  LLM classify │  subprocess, $$ per call  │
│                          └───────┬───────┘                           │
│                                  │                                   │
│                  validated=True/False  or  low_confidence            │
│                                  │                                   │
│                                  ▼                                   │
│                          ┌───────────────┐                           │
│                          │  human review │  the small leftover edge  │
│                          └───────────────┘                           │
│                                                                      │
│  fire fires (.fscars/logs/fires.jsonl)                               │
│        │                                                             │
│        └──▶  fscars.validation.cross_link  ──▶  opp.fire_matched     │
│        └──▶  fscars.validation.outcome     ──▶  fire.outcome         │
└──────────────────────────────────────────────────────────────────────┘
```

## Capa 4 — deterministic rules

Cheap, predictable, no external dependencies. One callable per scar examines
an opportunity dict and returns ``(verdict, reason)``:

```python
from fscars.validation import RulesEngine, apply_decisions

def classify_my_scar(opp: dict) -> tuple[str, str]:
    notes = opp.get("notes", "")
    if "trivial" in notes:
        return "auto_fp", "marker says trivial"
    return "ambiguous", "needs deeper look"

engine = RulesEngine()
engine.register("scar_my_thing", classify_my_scar)

decisions = engine.classify_all(opps)        # parallel-shape list
apply_decisions(opps, decisions)             # mutates rows in place
```

`apply_decisions` writes `auto_classification`, `auto_classification_reason`,
`auto_classified_at`. For `auto_tp` and `auto_fp` it also sets `validated`,
`validated_by`, and `validated_at`. `ambiguous` rows get the metadata but
leave `validated` untouched so Capa 3 can still decide.

Production data showed Capa 4 resolves the bulk of clearly-true and
clearly-false cases. The leftover `ambiguous` slice is what costs LLM
inference and human review.

## Capa 3 — LLM classifier (subprocess)

For the slice Capa 4 can't decide, we invoke an LLM through the local
`claude` CLI. The classifier:

* builds a prompt from a configurable template + scar description;
* calls `claude -p --model <model>` via `subprocess.run` with `text=True,
  encoding="utf-8", errors="replace"` (cp1252 default eats non-ASCII on
  Windows);
* parses a JSON verdict `{"validated": bool, "confidence": float,
  "reason": str}`;
* writes `validated` only when `confidence` clears the threshold (default
  0.8), tags everything else `low_confidence` for a human.

```python
from fscars.validation import LLMClassifier
from fscars.validation.llm import apply_verdict

def resolve_file(opp: dict) -> str | None:
    # Returning None skips the LLM call for that row (file not found).
    path = opp.get("file_path")
    return Path(path).read_text(encoding="utf-8", errors="replace") if path else None

clf = LLMClassifier(
    scar_descriptions={"scar_my_thing": "the human-readable scar rule"},
    file_resolver=resolve_file,
    model="haiku",      # or sonnet for stickier cases
    workers=4,          # subprocess parallelism — safe (no shared state)
    threshold=0.8,
)

for verdict in clf.classify_many(ambiguous_opps):
    apply_verdict(opps_by_event_id[verdict.event_id], verdict,
                  threshold=clf.threshold, timestamp=now_iso, model=clf.model)
```

The `claude` shim is resolved via `shutil.which("claude")` so Windows
`.cmd`/`.ps1` wrappers work without `shell=True`.

## Capa 5 — cross-link fires ↔ opportunities

Observation captures *opportunity* (the scar *could* fire). The actual hook
emits a *fire* when it *did* fire. Joining them gives confirmed hits vs.
missed catches:

```python
from fscars.validation import cross_link_fires_opps
from fscars.validation.cross_link import real_coverage

stats = cross_link_fires_opps(fires, opps, window_sec=5, dedup=True)
# Mutates opps in place with fire_matched / fire_event_id / fire_match_method
# Each fire matches at most one opp (chronological, stable).

cov = real_coverage(opps)
# {scar_id: {"matched": N, "missed": N, "coverage": M/(M+missed)}}
```

`missed` = opportunities where Capa 3 or 4 confirmed `validated=True` *and*
no fire matched within the time window. That is the real recall denominator
(not just total opps, which over-counts because most opps were noise).

## Outcome marking

Once a fire has been observed, label it post-hoc:

```python
from fscars.validation import OutcomeMarker

marker = OutcomeMarker()
marker.register("scar_my_thing", my_outcome_classifier)

decisions = marker.classify_many(fires)
marker.apply(fires, decisions)
```

Allowed outcomes:

* `error_prevented` — fire caught a real error.
* `false_positive` — fire was noise.
* `error_repeated` — hook missed and the error happened.
* `error_despite_fire` — hook fired but the error still slipped through.
* `unknown` — not yet classified.

`OutcomeMarker.mark_manually(fires, event_id, outcome)` sets the human
review flag, after which `classify_many(skip_marked=True)` (default) leaves
the row alone.

## Dashboard

Once opps and fires are labelled, `fscars.dashboard` renders both a
markdown summary and a self-contained HTML report:

```python
from fscars.dashboard import compute_metrics, render_html, render_markdown, filter_period

fires = filter_period(all_fires, "30d")
opps = filter_period(all_opps, "30d")
metrics = compute_metrics(fires, opps, period="30d")

md_text = render_markdown(metrics, title="my project — last 30 days")
html_text = render_html(metrics, title="my project", brand={"primary": "#0F1A2E"})
```

The palette is parametric — pass any subset of
`{"primary", "background", "accent", "secondary", "ok", "warn", "danger",
"muted"}` to override the neutral default.

## CLI shortcut

For the common pipeline, three commands cover the workflow end to end:

```bash
fscar validate --classifiers myapp.scars:register --apply
fscar dashboard --period 30d
fscar audit --classifiers myapp.scars:register
```

`fscar audit` chains Capa 4 → cross-link → dashboard. It does **not**
invoke Capa 3 by default (subprocess + cost) — run `fscar validate` and
your own LLM step when ready.

## Safe concurrent writes

All four modules mutate `opportunities.jsonl` or `fires.jsonl`. Naive
load-mutate-save races: two processes both load the snapshot, mutate
in-memory, and the last writer wins, dropping the other's fields.

`fscars.io.safe_jsonl.safe_save_jsonl` solves this with an
`O_EXCL`-acquired lock file, re-load on entry, field-level merge keyed by
`event_id`, and atomic temp + `os.replace`. Stale locks older than 120s are
auto-broken so a crashed writer cannot deadlock the pipeline.

Use it whenever your scripts write to a shared JSONL the rest of the
pipeline consumes.
