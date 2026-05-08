"""Claude Code adapter — Anthropic's claude-code CLI.

Reads JSON from stdin in the shape Claude Code uses and writes
hookSpecificOutput in the shape it expects.

Reference: Claude Code hooks documentation
https://docs.anthropic.com/claude/docs/claude-code/hooks
"""

from __future__ import annotations

import json
from pathlib import Path

from fscars.adapters.base import Adapter
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import ScarOutput

# Map Claude Code event names → canonical fscars event types
_CC_TO_CANONICAL = {
    "SessionStart": HookEventType.SESSION_START,
    "SessionEnd": HookEventType.SESSION_END,
    "UserPromptSubmit": HookEventType.USER_PROMPT_SUBMIT,
    "PreToolUse": HookEventType.PRE_TOOL_USE,
    "PostToolUse": HookEventType.POST_TOOL_USE,
    "Stop": HookEventType.STOP,
    "Notification": HookEventType.NOTIFICATION,
}


class ClaudeCodeAdapter(Adapter):
    """Adapter for Anthropic Claude Code."""

    name = "claude_code"

    def parse_stdin(self, raw: dict) -> HookPayload | None:
        """Convert Claude Code's stdin payload to a normalized HookPayload."""
        if not isinstance(raw, dict):
            return None

        # Claude Code sometimes uses "hook_event_name", sometimes "event"
        event_name = (
            raw.get("hook_event_name")
            or raw.get("event")
            or raw.get("hookEventName")
            or ""
        )
        canonical = _CC_TO_CANONICAL.get(event_name)
        if canonical is None:
            return None

        try:
            return HookPayload(
                event_type=canonical,
                tool_name=raw.get("tool_name"),
                tool_input=raw.get("tool_input") or {},
                prompt=raw.get("prompt"),
                cwd=raw.get("cwd") or raw.get("workspace") or "",
                session_id=raw.get("session_id") or "",
                raw=raw,
            )
        except Exception:
            return None

    def emit_output(self, output: ScarOutput) -> str:
        """Build the JSON string Claude Code expects on stdout.

        On block, the run_hook script also exits with code 2 — the
        decision="block" field is for surface visibility.
        """
        if output.is_empty:
            return "{}"

        payload: dict = {}
        hook_specific: dict = {}
        if output.additional_context:
            hook_specific["additionalContext"] = output.additional_context
        if output.block:
            hook_specific["decision"] = "block"
        if hook_specific:
            payload["hookSpecificOutput"] = hook_specific
        if output.system_message:
            payload["systemMessage"] = output.system_message
        return json.dumps(payload, ensure_ascii=False)

    # -----------------------------------------------------------------
    # install / uninstall — wire up `.claude/settings.json`
    # -----------------------------------------------------------------

    SETTINGS_FILE = ".claude/settings.json"
    HOOK_COMMAND = "python -m fscars.run_hook --adapter claude_code"

    def install(self, project_root: Path) -> None:
        """Add fscars entries to .claude/settings.json under project_root.

        Idempotent: re-running install does not duplicate entries.
        """
        settings_path = project_root / self.SETTINGS_FILE
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                settings = {}
        else:
            settings = {}

        hooks = settings.setdefault("hooks", {})

        wanted_events = (
            "SessionStart",
            "UserPromptSubmit",
            "PreToolUse",
            "PostToolUse",
            "Stop",
        )
        entry = {"command": self.HOOK_COMMAND}

        for event in wanted_events:
            current = hooks.get(event) or []
            if not isinstance(current, list):
                current = [current]
            already = any(
                isinstance(c, dict) and c.get("command") == self.HOOK_COMMAND
                for c in current
            )
            if not already:
                current.append(entry)
            hooks[event] = current

        settings_path.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def uninstall(self, project_root: Path) -> None:
        """Remove fscars entries from .claude/settings.json. Leaves other hooks alone."""
        settings_path = project_root / self.SETTINGS_FILE
        if not settings_path.exists():
            return
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return

        hooks = settings.get("hooks") or {}
        for event, entries in list(hooks.items()):
            if not isinstance(entries, list):
                continue
            kept = [
                e
                for e in entries
                if not (isinstance(e, dict) and e.get("command") == self.HOOK_COMMAND)
            ]
            if kept:
                hooks[event] = kept
            else:
                hooks.pop(event)
        if hooks:
            settings["hooks"] = hooks
        elif "hooks" in settings:
            settings.pop("hooks")

        settings_path.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


__all__ = ["ClaudeCodeAdapter"]
