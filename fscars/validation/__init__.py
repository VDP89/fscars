"""Validation layers for opportunity classification.

Three-tier loop developed in production at DG Ingenieria SRL (May 2026):

* **Capa 4** (:mod:`fscars.validation.rules`): deterministic rules per scar.
  Resolves the bulk of clearly-true / clearly-false candidates.
* **Capa 3** (:mod:`fscars.validation.llm`): LLM classifier for ambiguous rows.
* **Capa 5** (:mod:`fscars.validation.cross_link`): observer-to-fire matching
  so opportunities can be tagged with the actual hook fire they predicted.
* **Outcome** (:mod:`fscars.validation.outcome`): retroactive outcome marker
  for fires that were prevented vs false-positives.

All modules consume and produce raw ``dict`` rows so they can be wired to
JSONL stores or in-memory pipelines uniformly.
"""

from fscars.validation.cross_link import cross_link_fires_opps
from fscars.validation.llm import LLMClassifier, LLMVerdict
from fscars.validation.outcome import OutcomeMarker
from fscars.validation.rules import RulesEngine, Verdict, apply_decisions

__all__ = [
    "LLMClassifier",
    "LLMVerdict",
    "OutcomeMarker",
    "RulesEngine",
    "Verdict",
    "apply_decisions",
    "cross_link_fires_opps",
]
