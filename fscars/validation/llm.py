"""Capa 3 — LLM classifier for opportunities marked ``ambiguous`` by Capa 4.

Workflow:

1. Take an opportunity row whose Capa 4 verdict was ``ambiguous``.
2. Build a prompt from a template + an opportunity-specific context (file
   content, notes, scar description, ...).
3. Invoke an LLM via subprocess (the ``claude`` CLI by default) and parse a
   JSON verdict ``{"validated": bool, "confidence": float, "reason": str}``.
4. If ``confidence`` clears the threshold, mark the opportunity as validated;
   otherwise tag it ``low_confidence`` for human review.

The subprocess wrapper hardens against two Windows-on-Python gotchas:

* :func:`shutil.which` resolves the ``claude`` shim (``.cmd``/``.ps1``) on
  Windows, which :func:`subprocess.run` with ``shell=False`` would miss.
* ``encoding="utf-8"`` + ``errors="replace"`` avoid the default ``cp1252``
  decode that explodes the moment a non-ASCII byte shows up in stdout.

The classifier itself is stateless apart from the configuration object —
threading via :class:`ThreadPoolExecutor` is safe because each call shells
out to an external process.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Literal

LLMStatus = Literal["ok", "parse_fail", "skipped_file_not_found", "error"]

DEFAULT_PROMPT_TEMPLATE = """\
You are a classifier deciding whether an "opportunity" captured by an
observer is a real case where the named scar applies, or a false positive.

SCAR: {scar_id} — {scar_desc}

OPPORTUNITY:
- file: {filename}
- tool: {tool_name}
- notes: {notes}
- context: {project_context}

FILE CONTENT (first {content_len} chars):
```
{file_content}
```

Reply with EXACTLY this JSON, no markdown fences, no prose outside the JSON:
{{"validated": true|false, "confidence": 0.0-1.0, "reason": "<one line, <=100 chars>"}}

- validated=true  → the scar applies to this case (should fire).
- validated=false → false positive (should not fire).
- confidence: 0.0 (no idea) to 1.0 (certain).
- reason: one short line explaining why.
"""


@dataclass
class LLMVerdict:
    """Result of a single LLM classification call."""

    event_id: str | None
    status: LLMStatus
    validated: bool | None = None
    confidence: float = 0.0
    reason: str = ""
    raw_response: str = ""


FileResolver = Callable[[dict], str | None]
"""Callable that returns the textual content for an opportunity, or ``None``
if no file could be resolved (in which case the row is tagged
``skipped_file_not_found`` without an LLM call).
"""


@dataclass
class LLMClassifier:
    """Wrap a subprocess-based LLM call as a per-opportunity classifier.

    Attributes:
        scar_descriptions: ``scar_id → human-readable description``. The
            description is interpolated into the prompt so the LLM knows
            what behaviour the scar is meant to catch.
        file_resolver: Function that returns the file content (or any
            context blob) for a given opportunity. Returning ``None`` skips
            the LLM call.
        model: Model name passed to ``claude -p --model``.
        threshold: Minimum confidence required to write ``validated``.
        claude_cli: Override the CLI binary. Empty (default) resolves to
            ``shutil.which("claude")`` so Windows ``.cmd`` shims work.
        timeout_sec: Subprocess timeout for one call.
        content_max_chars: Truncate file content before embedding in the
            prompt to bound prompt size and cost.
        prompt_template: Customisable prompt template; must accept the
            placeholders used by :data:`DEFAULT_PROMPT_TEMPLATE`.
        notes_field, scar_id_field, event_id_field: Names of the
            corresponding fields on the opportunity dict.
        workers: Parallel subprocess workers for :meth:`classify_many`.
    """

    scar_descriptions: dict[str, str] = field(default_factory=dict)
    file_resolver: FileResolver | None = None
    model: str = "haiku"
    threshold: float = 0.8
    claude_cli: str = ""  # resolved in __post_init__ if empty
    timeout_sec: int = 90
    content_max_chars: int = 1500
    prompt_template: str = DEFAULT_PROMPT_TEMPLATE
    notes_field: str = "notes"
    scar_id_field: str = "scar_id"
    event_id_field: str = "event_id"
    tool_name_field: str = "tool_name"
    project_context_field: str = "project_context"
    filename_extractor: Callable[[str], str] = field(
        default=lambda notes: notes.split(":", 1)[1].strip()
        if ":" in notes
        else ""
    )
    workers: int = 1

    def __post_init__(self) -> None:
        if not self.claude_cli:
            self.claude_cli = shutil.which("claude") or "claude"

    def build_prompt(self, opp: dict, file_content: str) -> str:
        scar_id = opp.get(self.scar_id_field, "")
        return self.prompt_template.format(
            scar_id=scar_id,
            scar_desc=self.scar_descriptions.get(scar_id, "?"),
            filename=self.filename_extractor(opp.get(self.notes_field, "")),
            tool_name=opp.get(self.tool_name_field, ""),
            notes=opp.get(self.notes_field, ""),
            project_context=opp.get(self.project_context_field, ""),
            content_len=len(file_content),
            file_content=file_content[: self.content_max_chars],
        )

    def _call_subprocess(self, prompt: str) -> str:
        try:
            result = subprocess.run(
                [self.claude_cli, "-p", "--model", self.model],
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_sec,
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return ""
        except (FileNotFoundError, OSError) as exc:
            return f"__ERROR__: {exc}"

    @staticmethod
    def _parse_response(text: str) -> dict | None:
        if not text or text.startswith("__ERROR__"):
            return None
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
        if "validated" in data and "confidence" in data:
            return data
        return None

    def classify_one(self, opp: dict) -> LLMVerdict:
        eid = opp.get(self.event_id_field)
        content = self.file_resolver(opp) if self.file_resolver else ""
        if content is None:
            return LLMVerdict(event_id=eid, status="skipped_file_not_found")

        prompt = self.build_prompt(opp, content)
        raw = self._call_subprocess(prompt)
        if raw.startswith("__ERROR__"):
            return LLMVerdict(event_id=eid, status="error", raw_response=raw)
        parsed = self._parse_response(raw)
        if parsed is None:
            return LLMVerdict(
                event_id=eid, status="parse_fail", raw_response=raw[:300]
            )
        return LLMVerdict(
            event_id=eid,
            status="ok",
            validated=bool(parsed.get("validated")),
            confidence=float(parsed.get("confidence", 0.0)),
            reason=str(parsed.get("reason", ""))[:100],
            raw_response=raw[:300],
        )

    def classify_many(
        self,
        opps: Iterable[dict],
    ) -> Iterator[LLMVerdict]:
        """Yield verdicts as they complete. Order is not preserved when
        ``workers > 1`` — match by ``event_id`` to apply results.
        """
        opps_list = list(opps)
        if self.workers <= 1:
            for opp in opps_list:
                yield self.classify_one(opp)
            return

        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futures = [ex.submit(self.classify_one, opp) for opp in opps_list]
            for fut in as_completed(futures):
                yield fut.result()


def apply_verdict(
    opp: dict,
    verdict: LLMVerdict,
    *,
    threshold: float,
    timestamp: str,
    model: str,
) -> bool:
    """Mutate ``opp`` with LLM metadata. Returns True if ``validated`` was set.

    Threshold gating: ``validated`` is only written when ``status == "ok"`` and
    ``confidence >= threshold``. Otherwise the row keeps Capa 4's verdict
    (typically ``ambiguous``) and gets an ``llm_classification`` tag so an
    operator can see why no decision was made.
    """
    opp["llm_classified_at"] = timestamp
    opp["llm_model"] = model
    if verdict.status == "skipped_file_not_found":
        opp["llm_classification"] = "skipped_file_not_found"
        return False
    if verdict.status == "parse_fail":
        opp["llm_classification"] = "parse_fail"
        opp["llm_raw_response"] = verdict.raw_response
        return False
    if verdict.status == "error":
        opp["llm_classification"] = "error"
        opp["llm_raw_response"] = verdict.raw_response
        return False
    opp["llm_classification"] = "ok"
    opp["llm_validated"] = verdict.validated
    opp["llm_confidence"] = verdict.confidence
    opp["llm_reason"] = verdict.reason
    if verdict.confidence >= threshold:
        opp["validated"] = verdict.validated
        opp["validated_by"] = f"capa_3_llm_{model}"
        opp["validated_at"] = timestamp
        return True
    opp["llm_classification"] = "low_confidence"
    return False


__all__ = [
    "DEFAULT_PROMPT_TEMPLATE",
    "FileResolver",
    "LLMClassifier",
    "LLMStatus",
    "LLMVerdict",
    "apply_verdict",
]
