# Contributing to fscars

Thanks for taking the time to look. fscars is in alpha — feedback shapes the
1.0 design and we welcome it.

## Quick local setup

```bash
git clone https://github.com/Vdp89/fscars
cd fscars
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
pytest -q
ruff check fscars cookbook tests
```

## Three good first issues

| Type | What to do |
| --- | --- |
| New starter scar | Copy `cookbook/scars/_template.py`, fill it in, add tests, open PR |
| Doc improvement | Anywhere a doc says "TODO" or assumes context — clarify |
| Adapter | Pick a platform from the roadmap (Codex, Cursor, Aider, Continue.dev) and start a draft adapter |

## Pull request checklist

- [ ] `pytest -q` passes locally
- [ ] `ruff check fscars cookbook tests` is clean
- [ ] If you added a starter scar, you also added a unit test for it
- [ ] If you changed log schema, you bumped `SCHEMA_VERSION` in `fscars/core/fire.py`
  and added a migration note to `CHANGELOG.md`
- [ ] PR description explains the *why*, not only the *what*

## What we do **not** want

- Pricing tiers, login, hosted SaaS.
- A "smart" engine that auto-applies scars without operator approval.
- Heuristic guess fields in `fires.jsonl` — when in doubt, emit `null` and
  let the analyser interpret. Guessing introduces bias into recall.

## Code of conduct

By participating you agree to abide by our
[Code of Conduct](.github/CODE_OF_CONDUCT.md).

## Releasing

Maintainers only. The full procedure (including the one-time PyPI trusted
publisher setup) is in [RELEASE.md](RELEASE.md).
