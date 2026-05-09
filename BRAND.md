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

## Palette (refined v2 — DG navy + Anthropic warm fusion)

| Token | Hex | Use |
| --- | --- | --- |
| Navy | `#0F1A2E` | Primary dark, glyph background, wordmark on light |
| Cream | `#F5F1E8` | Light backgrounds, glyph foreground |
| Terracota | `#CC785C` | Primary accent — scar line, stitches, identity mark |
| Slate | `#475569` | Tagline, secondary text |
| Slate light | `#94A3B8` | Tagline on dark backgrounds |
| Mint | `#10B981` | "Passed" / OK semantics in CLI output |
| Red | `#DC2626` | Reserved for CLI "blocked" semantics only — NOT a brand asset color |

The terracota is the fusion the brand sits on: warm enough to belong with
Anthropic's coral palette, dark enough to anchor next to DG's navy infra
mark. It carries the scar line — a horizontal stroke crossed by four
stitches — which is the identifying mark across logo, icon, and any future
brand surface.

Red `#DC2626` stays explicitly out of the brand assets. It is a semantic
color reserved for the CLI, where a scar that blocks a tool call uses red
to say "blocked, do not proceed." Mixing it into the logo would dilute that
signal.

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
