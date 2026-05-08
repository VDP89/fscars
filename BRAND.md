# Brand guidelines

These are working notes. Logo and final palette are pending external design
input — the decisions here freeze a default, not a finished system.

## Voice

- Direct, technical, no jargon-as-jargon.
- Honest about limits — the README has a *When NOT to use fscars* section
  and we keep it.
- No "revolutionary", no "10x", no marketing superlatives.
- We describe what the product **does**, not what it avoids.
  (See `cookbook/scars/avoid_negative_framing.py` — we eat our own food.)

## Naming

- **Functional Scars** — product, plural, mixed case.
- **scar** — individual unit, lowercase, plural OK.
- **fscars** — the Python package and the repo name.
- **fscar** — the CLI command (singular, like `git`).

## Palette (provisional — option B from the planning doc)

| Token | Hex | Use |
| --- | --- | --- |
| Charcoal | `#1F2937` | Primary text, dark backgrounds |
| Cream | `#FAF7F0` | Light backgrounds, cards |
| Red | `#DC2626` | "Blocked" semantics, critical accents |
| Slate | `#475569` | Secondary text |
| Mint | `#10B981` | "Passed" / OK semantics |

The red is intentional: a scar that blocks a tool call needs an unambiguous
visual signal. Compare to Anthropic Memory which uses neutral blue — fscars
is louder by design.

## Typography

- Headings: **Inter** (free, web-safe, clean).
- Code: **JetBrains Mono** or **Fira Code**.
- Body: Inter.

## What the product is not

- It is not a SaaS.
- It is not a model — there is no learning, no inference, no training data
  collection.
- It is not magic — every action is logged, deterministic, traceable.

## Footer attribution

Every public surface (README, docs site, blog post about fscars) must link
to the [Lucy Syndrome paper](https://doi.org/10.5281/zenodo.19555971). The
research is the reason fscars exists.
