# Contributors

Functional Scars is built and maintained by:

- **[Victor Del Puerto](https://victordelpuerto.com)** — author and maintainer.
  The engine, validation layers, and cookbook come out of production operation
  at **[DG Ingeniería SRL](https://dgingenieriasrl.com)**.

## Acknowledgments

- **OpenAI Codex** designed and implemented the original Codex instruction-mode
  adapter ([`fscars/adapters/codex/`](fscars/adapters/codex/),
  [#6](https://github.com/VDP89/fscars/pull/6)). It mapped out and built its own
  path into fscars: the idempotent `AGENTS.md` install block, the
  `.codex/fscars.json` manifest, and the integration plan in
  [`docs/codex_integration_plan.md`](docs/codex_integration_plan.md). Codex also
  ran the out-of-band review that approved the v0.4.0 native-hooks promotion
  ([#7](https://github.com/VDP89/fscars/pull/7)).
- The framework is grounded in the companion paper
  [*Lucy Syndrome in LLM Agents*](https://doi.org/10.5281/zenodo.19555971).

Routine dependency bumps and asset regeneration are handled by automation
(Dependabot, GitHub Actions) and are not listed as contributors here.

New adapters and cookbook scars are especially welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md).
