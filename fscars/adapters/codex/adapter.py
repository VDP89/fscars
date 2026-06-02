"""Codex adapter — OpenAI's Codex coding agent.

Codex does not currently expose the same stable tool-hook contract used by
Claude Code, so the production installer works in instruction mode: it writes
an idempotent ``AGENTS.md`` block plus a machine-readable manifest under
``.codex/fscars.json``. The parse/emit methods still support a normalized JSON
shape so future hook support can be enabled without changing the core engine.
"""

from __future__ import annotations

import json
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fscars.adapters.base import Adapter
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import ScarOutput

_CODEX_TO_CANONICAL = {
    "SessionStart": HookEventType.SESSION_START,
    "SessionEnd": HookEventType.SESSION_END,
    "UserPromptSubmit": HookEventType.USER_PROMPT_SUBMIT,
    "PreToolUse": HookEventType.PRE_TOOL_USE,
    "PostToolUse": HookEventType.POST_TOOL_USE,
    "Stop": HookEventType.STOP,
    "Notification": HookEventType.NOTIFICATION,
    # Lowercase aliases are convenient for wrapper scripts and tests.
    "session_start": HookEventType.SESSION_START,
    "session_end": HookEventType.SESSION_END,
    "user_prompt_submit": HookEventType.USER_PROMPT_SUBMIT,
    "pre_tool_use": HookEventType.PRE_TOOL_USE,
    "post_tool_use": HookEventType.POST_TOOL_USE,
    "stop": HookEventType.STOP,
    "notification": HookEventType.NOTIFICATION,
}


class CodexAdapter(Adapter):
    """Adapter for OpenAI Codex.

    The adapter intentionally separates two capabilities:

    * ``install``/``uninstall`` are stable today and manage Codex project
      instructions via ``AGENTS.md``.
    * ``parse_stdin``/``emit_output`` are the hook-facing contract used by
      tests and future Codex hook wrappers.
    """

    name = "codex"

    AGENTS_FILE = "AGENTS.md"
    MANIFEST_FILE = ".codex/fscars.json"
    HOOK_COMMAND = "python -m fscars.run_hook --adapter codex"
    BLOCK_START = "<!-- fscars:codex:start -->"
    BLOCK_END = "<!-- fscars:codex:end -->"

    def parse_stdin(self, raw: dict[str, Any]) -> HookPayload | None:
        """Convert a Codex/wrapper JSON payload to a normalized HookPayload."""
        if not isinstance(raw, dict):
            return None
        event_name = (
            raw.get("hook_event_name")
            or raw.get("event")
            or raw.get("hookEventName")
            or raw.get("type")
            or ""
        )
        canonical = _CODEX_TO_CANONICAL.get(str(event_name))
        if canonical is None:
            return None

        try:
            return HookPayload(
                event_type=canonical,
                tool_name=raw.get("tool_name") or raw.get("toolName"),
                tool_input=raw.get("tool_input") or raw.get("toolInput") or {},
                prompt=raw.get("prompt"),
                cwd=raw.get("cwd") or raw.get("workspace") or "",
                session_id=raw.get("session_id") or raw.get("sessionId") or "",
                raw=raw,
            )
        except Exception:
            return None

    def emit_output(self, output: ScarOutput) -> str:
        """Serialize ScarOutput as generic JSON for Codex wrappers.

        Instruction-mode installs do not consume this directly, but keeping a
        small JSON contract makes the adapter ready for a future native hook.
        """
        if output.is_empty:
            return "{}"
        payload: dict[str, str | bool] = {}
        if output.additional_context:
            payload["additional_context"] = output.additional_context
        if output.system_message:
            payload["system_message"] = output.system_message
        if output.block:
            payload["decision"] = "block"
            payload["block"] = True
        return json.dumps(payload, ensure_ascii=False)

    def install(self, project_root: Path) -> None:
        """Install fscars guidance for Codex in AGENTS.md.

        The block is idempotent and scoped to the project root. It tells Codex
        how to use fscars as a preflight/audit tool until Codex exposes a stable
        native hook surface.
        """
        project_root.mkdir(parents=True, exist_ok=True)
        agents_path = project_root / self.AGENTS_FILE
        manifest_path = project_root / self.MANIFEST_FILE

        current = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
        block = self._agents_block()
        updated = self._replace_or_append_block(current, block)
        agents_path.write_text(updated, encoding="utf-8")

        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 1,
            "adapter": self.name,
            "mode": "instructions",
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "agents_file": self.AGENTS_FILE,
            "hook_command": self.HOOK_COMMAND,
            "native_hook_status": "pending_codex_stable_hook_api",
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def uninstall(self, project_root: Path) -> None:
        """Remove the AGENTS.md fscars block and Codex manifest."""
        agents_path = project_root / self.AGENTS_FILE
        if agents_path.exists():
            current = agents_path.read_text(encoding="utf-8")
            updated = self._remove_block(current).strip()
            if updated:
                agents_path.write_text(updated + "\n", encoding="utf-8")
            else:
                agents_path.unlink()

        manifest_path = project_root / self.MANIFEST_FILE
        if manifest_path.exists():
            manifest_path.unlink()
            codex_dir = manifest_path.parent
            with suppress(OSError):
                codex_dir.rmdir()

    @classmethod
    def _agents_block(cls) -> str:
        return "\n".join(
            [
                cls.BLOCK_START,
                "## Functional Scars for Codex",
                "",
                "This repository uses `fscars` to make repeated corrections persistent.",
                "Until Codex exposes a stable native hook API, treat this block as the",
                "Codex integration contract for every task in this repo.",
                "",
                "- Before final delivery, run `fscar audit --period 30d` when `.fscars/` exists.",
                "- If a task edits scar-sensitive files, inspect `.fscars/logs/fires.jsonl` and",
                "  `.fscars/logs/opportunities.jsonl` before summarizing results.",
                "- When you find a repeated, binary correction, propose or add a new scar under",
                "  `cookbook/scars/` and cover it with tests.",
                "- Do not ignore a scar warning silently: either fix the issue or mention why the",
                "  warning is a false positive in the final response.",
                "- Native hook command reserved for future Codex hook support:",
                f"  `{cls.HOOK_COMMAND}`.",
                cls.BLOCK_END,
                "",
            ]
        )

    @classmethod
    def _replace_or_append_block(cls, current: str, block: str) -> str:
        current = current.replace("\r\n", "\n")
        start = current.find(cls.BLOCK_START)
        end = current.find(cls.BLOCK_END)
        if start != -1 and end != -1 and end > start:
            end += len(cls.BLOCK_END)
            updated = current[:start].rstrip() + "\n\n" + block.rstrip() + current[end:].rstrip()
            return updated.rstrip() + "\n"
        if current.strip():
            return current.rstrip() + "\n\n" + block
        return block

    @classmethod
    def _remove_block(cls, current: str) -> str:
        current = current.replace("\r\n", "\n")
        start = current.find(cls.BLOCK_START)
        end = current.find(cls.BLOCK_END)
        if start == -1 or end == -1 or end <= start:
            return current
        end += len(cls.BLOCK_END)
        return current[:start].rstrip() + "\n\n" + current[end:].lstrip()


__all__ = ["CodexAdapter"]
