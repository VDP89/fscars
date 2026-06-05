"""Codex adapter — OpenAI's Codex coding agent.

Codex now exposes a native hook contract (``~/.codex/hooks.json`` or a repo
``.codex/hooks.json``) with the same matcher-group shape Claude Code uses.
``install`` registers a single fscars entrypoint as a native ``command`` hook
for every parity event, so scars can block deterministically on the surfaces
Codex supports. Two deny surfaces are wired: ``PreToolUse`` (deny a
``Bash``/``apply_patch``/MCP call before it runs) and ``PermissionRequest``
(the dedicated approval surface — a scar's ``deny`` keeps the request from
being approved). The ``AGENTS.md`` block is kept as an operational fallback and
audit-loop contract, not the primary mechanism.

Reference: https://developers.openai.com/codex/hooks

Limitations carried from upstream: Codex ``PreToolUse`` is a guardrail, not a
complete boundary — it does not intercept every shell path yet, and WebSearch
and other non-shell/non-MCP tools are not intercepted. Non-managed command
hooks must be trusted once via ``/hooks`` in the Codex CLI before they run.
"""

from __future__ import annotations

import json
import re
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
    "PermissionRequest": HookEventType.PERMISSION_REQUEST,
    "Stop": HookEventType.STOP,
    "SubagentStop": HookEventType.SUBAGENT_STOP,
    "Notification": HookEventType.NOTIFICATION,
    # Lowercase aliases are convenient for wrapper scripts and tests.
    "session_start": HookEventType.SESSION_START,
    "session_end": HookEventType.SESSION_END,
    "user_prompt_submit": HookEventType.USER_PROMPT_SUBMIT,
    "pre_tool_use": HookEventType.PRE_TOOL_USE,
    "post_tool_use": HookEventType.POST_TOOL_USE,
    "permission_request": HookEventType.PERMISSION_REQUEST,
    "stop": HookEventType.STOP,
    "subagent_stop": HookEventType.SUBAGENT_STOP,
    "notification": HookEventType.NOTIFICATION,
}

# Codex edits files through `apply_patch`. The cookbook scars target the
# Write/Edit tool names, so we present apply_patch as "Edit" while keeping the
# original Codex tool name in `raw`.
_APPLY_PATCH_NAMES = {"apply_patch", "applyPatch"}

# `*** Add File: path`, `*** Update File: path`, `*** Delete File: path`
_PATCH_PATH_RE = re.compile(
    r"^\*\*\*\s+(?:Add|Update|Delete)\s+File:\s+(.+?)\s*$",
    re.MULTILINE,
)


class CodexAdapter(Adapter):
    """Adapter for OpenAI Codex with native hook support.

    * ``install``/``uninstall`` register a native ``command`` hook in
      ``.codex/hooks.json`` and keep an ``AGENTS.md`` operating block as a
      fallback/audit contract.
    * ``parse_stdin``/``emit_output`` implement the Codex hook payload and the
      Codex response schema (``permissionDecision``/``additionalContext``).
    """

    name = "codex"

    AGENTS_FILE = "AGENTS.md"
    MANIFEST_FILE = ".codex/fscars.json"
    HOOKS_FILE = ".codex/hooks.json"
    HOOK_COMMAND = "python -m fscars.run_hook --adapter codex"
    HOOK_COMMAND_WINDOWS = "py -3 -m fscars.run_hook --adapter codex"
    STATUS_MESSAGE = "fscars functional-scar check"
    BLOCK_START = "<!-- fscars:codex:start -->"
    BLOCK_END = "<!-- fscars:codex:end -->"

    # Same five surfaces the Claude Code adapter wires.
    WANTED_EVENTS: tuple[str, ...] = (
        "SessionStart",
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "PermissionRequest",
        "Stop",
        "SubagentStop",
    )

    # ------------------------------------------------------------------
    # Hook-facing contract
    # ------------------------------------------------------------------

    def parse_stdin(self, raw: dict[str, Any]) -> HookPayload | None:
        """Convert a Codex hook JSON payload to a normalized HookPayload."""
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

        tool_name = raw.get("tool_name") or raw.get("toolName")
        tool_input = dict(raw.get("tool_input") or raw.get("toolInput") or {})

        # Surface a concrete file_path so path-scoped scars can match, and bridge
        # apply_patch into the Write/Edit world the cross-platform cookbook scars
        # expect. The rename is skipped for PermissionRequest: that surface is
        # Codex-specific, so a scar there matches on Codex's canonical tool name
        # (`apply_patch`) — renaming it to "Edit" would make tool_matchers
        # =("apply_patch",) silently miss.
        if tool_name in _APPLY_PATCH_NAMES:
            patched = self._first_patched_path(tool_input)
            if patched and not tool_input.get("file_path"):
                tool_input["file_path"] = patched
            if canonical != HookEventType.PERMISSION_REQUEST:
                tool_name = "Edit"

        try:
            return HookPayload(
                event_type=canonical,
                tool_name=tool_name,
                tool_input=tool_input,
                prompt=raw.get("prompt"),
                cwd=raw.get("cwd") or raw.get("workspace") or "",
                session_id=raw.get("session_id") or raw.get("sessionId") or "",
                raw=raw,
            )
        except Exception:
            return None

    @staticmethod
    def _first_patched_path(tool_input: dict[str, Any]) -> str:
        """Pull the first file path out of an apply_patch payload."""
        patch = tool_input.get("command") or tool_input.get("patch") or tool_input.get("input")
        if not patch:
            return ""
        match = _PATCH_PATH_RE.search(str(patch))
        return match.group(1).strip() if match else ""

    def emit_output(self, output: ScarOutput, payload: HookPayload | None = None) -> str:
        """Serialize ScarOutput in Codex's native hook response schema.

        * ``PermissionRequest`` block → nested ``decision: {"behavior": "deny",
          "message": ...}`` (the dedicated approval surface; any matching hook's
          ``deny`` wins). fscars never returns ``allow`` — that would suppress
          the user's approval prompt, which is not a scar's call to make — so a
          non-blocking PermissionRequest emits nothing.
        * ``PreToolUse`` block → ``permissionDecision: "deny"`` (the call is
          denied before it runs).
        * ``SubagentStop`` (and any other event) block → top-level
          ``decision: "block"`` + ``reason``: for ``SubagentStop`` this keeps the
          subagent running with that feedback; for other events the tool already
          ran. ``run_hook`` still exits 2 to signal the block upstream (a
          documented ``SubagentStop`` block path, unlike ``PermissionRequest``).
        * Non-blocking context is injected via ``additionalContext``.
        """
        if output.is_empty:
            return "{}"

        event_type = payload.event_type if payload is not None else HookEventType.PRE_TOOL_USE
        event_name = event_type.value

        if event_type == HookEventType.PERMISSION_REQUEST:
            if not output.block:
                # Deny-or-nothing: stay silent so Codex's normal approval flow
                # is untouched (no `allow`, no context injection on this surface).
                return "{}"
            message = (
                output.additional_context
                or output.system_message
                or "fscars: blocked by a functional scar."
            )
            decision_result: dict[str, Any] = {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "decision": {"behavior": "deny", "message": message},
                }
            }
            if output.system_message:
                decision_result["systemMessage"] = output.system_message
            return json.dumps(decision_result, ensure_ascii=False)

        is_pre_tool = event_type == HookEventType.PRE_TOOL_USE

        hook_specific: dict[str, Any] = {"hookEventName": event_name}
        result: dict[str, Any] = {}

        if output.block:
            if is_pre_tool:
                hook_specific["permissionDecision"] = "deny"
                hook_specific["permissionDecisionReason"] = (
                    output.additional_context
                    or output.system_message
                    or "fscars: blocked by a functional scar."
                )
            else:
                # The tool already ran (or there is no tool). Surface as
                # feedback: `decision: "block"` + top-level `reason` per the
                # official examples, mirrored into additionalContext.
                reason = (
                    output.additional_context
                    or output.system_message
                    or "fscars: blocked by a functional scar."
                )
                result["decision"] = "block"
                result["reason"] = reason
                if output.additional_context:
                    hook_specific["additionalContext"] = output.additional_context
        elif output.additional_context:
            hook_specific["additionalContext"] = output.additional_context

        result["hookSpecificOutput"] = hook_specific
        if output.system_message:
            result["systemMessage"] = output.system_message
        return json.dumps(result, ensure_ascii=False)

    # ------------------------------------------------------------------
    # install / uninstall
    # ------------------------------------------------------------------

    def install(self, project_root: Path) -> None:
        """Register native Codex hooks and keep the AGENTS.md fallback block.

        Idempotent: re-running install does not duplicate hooks or the block,
        and it preserves any non-fscars hooks already in ``.codex/hooks.json``.
        """
        project_root.mkdir(parents=True, exist_ok=True)

        # 1. AGENTS.md operating notes (fallback / audit contract).
        agents_path = project_root / self.AGENTS_FILE
        current = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
        agents_path.write_text(
            self._replace_or_append_block(current, self._agents_block()),
            encoding="utf-8",
        )

        # 2. Native hooks.json registration.
        hooks_path = project_root / self.HOOKS_FILE
        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        config = self._load_hooks_config(hooks_path)
        self._merge_fscars_hooks(config)
        hooks_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # 3. Machine-readable manifest.
        manifest_path = project_root / self.MANIFEST_FILE
        manifest = {
            "schema_version": 2,
            "adapter": self.name,
            "mode": "native-hooks",
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "agents_file": self.AGENTS_FILE,
            "hooks_file": self.HOOKS_FILE,
            "hook_command": self.HOOK_COMMAND,
            "events": list(self.WANTED_EVENTS),
            "native_hook_status": "installed_pending_codex_trust_review",
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def uninstall(self, project_root: Path) -> None:
        """Remove fscars hooks, the AGENTS.md block, and the manifest.

        Other hooks in ``.codex/hooks.json`` are left untouched.
        """
        # AGENTS.md block.
        agents_path = project_root / self.AGENTS_FILE
        if agents_path.exists():
            current = agents_path.read_text(encoding="utf-8")
            updated = self._remove_block(current).strip()
            if updated:
                agents_path.write_text(updated + "\n", encoding="utf-8")
            else:
                agents_path.unlink()

        # hooks.json — strip only fscars handlers.
        hooks_path = project_root / self.HOOKS_FILE
        if hooks_path.exists():
            config = self._load_hooks_config(hooks_path)
            if self._strip_fscars_hooks(config):
                hooks_path.unlink()
            else:
                hooks_path.write_text(
                    json.dumps(config, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

        # Manifest.
        manifest_path = project_root / self.MANIFEST_FILE
        if manifest_path.exists():
            manifest_path.unlink()

        # Drop .codex/ only if we emptied it.
        codex_dir = project_root / ".codex"
        if codex_dir.is_dir():
            with suppress(OSError):
                codex_dir.rmdir()

    # ------------------------------------------------------------------
    # hooks.json helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_hooks_config(path: Path) -> dict[str, Any]:
        """Read hooks.json defensively; an unreadable/invalid file → empty."""
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _handler(self) -> dict[str, Any]:
        return {
            "type": "command",
            "command": self.HOOK_COMMAND,
            "commandWindows": self.HOOK_COMMAND_WINDOWS,
            "statusMessage": self.STATUS_MESSAGE,
        }

    @staticmethod
    def _is_fscars_handler(handler: Any) -> bool:
        return isinstance(handler, dict) and "fscars.run_hook" in str(handler.get("command", ""))

    def _group_has_fscars(self, group: Any) -> bool:
        if not isinstance(group, dict):
            return False
        handlers = group.get("hooks")
        if not isinstance(handlers, list):
            return False
        return any(self._is_fscars_handler(h) for h in handlers)

    def _merge_fscars_hooks(self, config: dict[str, Any]) -> None:
        """Add the fscars handler to each parity event, idempotently."""
        hooks = config.get("hooks")
        if not isinstance(hooks, dict):
            hooks = {}
            config["hooks"] = hooks

        for event in self.WANTED_EVENTS:
            groups = hooks.get(event)
            if not isinstance(groups, list):
                groups = []
            if not any(self._group_has_fscars(g) for g in groups):
                groups.append({"hooks": [self._handler()]})
            hooks[event] = groups

    def _strip_fscars_hooks(self, config: dict[str, Any]) -> bool:
        """Remove fscars handlers from config in place.

        Returns True if the whole config is now empty (caller deletes the file).
        """
        hooks = config.get("hooks")
        if isinstance(hooks, dict):
            for event, groups in list(hooks.items()):
                if not isinstance(groups, list):
                    continue
                kept_groups: list[Any] = []
                for group in groups:
                    if not isinstance(group, dict):
                        kept_groups.append(group)
                        continue
                    handlers = group.get("hooks")
                    if not isinstance(handlers, list):
                        kept_groups.append(group)
                        continue
                    kept = [h for h in handlers if not self._is_fscars_handler(h)]
                    if kept:
                        group["hooks"] = kept
                        kept_groups.append(group)
                    # else: the group held only fscars handlers → drop it.
                if kept_groups:
                    hooks[event] = kept_groups
                else:
                    hooks.pop(event)
            if hooks:
                config["hooks"] = hooks
            else:
                config.pop("hooks", None)
        return not config

    # ------------------------------------------------------------------
    # AGENTS.md block (fallback / audit-loop contract)
    # ------------------------------------------------------------------

    @classmethod
    def _agents_block(cls) -> str:
        return "\n".join(
            [
                cls.BLOCK_START,
                "## Functional Scars for Codex",
                "",
                "This repository uses `fscars` with **native Codex hooks** "
                "(see `.codex/hooks.json`).",
                "Run `/hooks` in the Codex CLI once to review and trust them; "
                "Codex does not run non-managed hooks until you approve them.",
                "",
                "These notes are the operational fallback and audit contract:",
                "",
                "- Before final delivery, run `fscar audit --period 30d` when `.fscars/` exists.",
                "- If a task edits scar-sensitive files, inspect `.fscars/logs/fires.jsonl` and",
                "  `.fscars/logs/opportunities.jsonl` before summarizing results.",
                "- When you find a repeated, binary correction, propose or add a new scar under",
                "  `cookbook/scars/` and cover it with tests.",
                "- Do not ignore a scar warning silently: either fix the issue or mention why the",
                "  warning is a false positive in the final response.",
                "- Native hook entrypoint registered in `.codex/hooks.json`:",
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
