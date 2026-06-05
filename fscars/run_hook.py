"""Single hook entrypoint — `python -m fscars.run_hook`.

Reads the hook payload from stdin, dispatches through the adapter and the
engine, and writes the platform-formatted output to stdout. Exit code 2
when any matching scar blocks the tool call.

This replaces the per-scar hook script architecture from the original
Lucy Syndrome reference: settings.json wires this single command for every
event type, and the engine routes to whichever Scars match.
"""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from fscars.adapters.base import Adapter
from fscars.adapters.claude_code import ClaudeCodeAdapter
from fscars.adapters.codex import CodexAdapter
from fscars.core import engine
from fscars.core.engine import ScarRegistry
from fscars.core.payload import HookEventType
from fscars.core.store import default_store

_ADAPTERS: dict[str, type[Adapter]] = {
    "claude_code": ClaudeCodeAdapter,
    "codex": CodexAdapter,
}


def _force_utf8_io() -> None:
    """Force stdin/stdout to UTF-8 regardless of platform.

    On Windows the default console encoding is cp1252, so a scar message with
    a non-ASCII character (e.g. the em-dash in the ``large-write-review``
    starter scar) would be written as bytes the host agent cannot decode —
    byte ``0x97`` instead of the UTF-8 sequence ``e2 80 94``. Codex and Claude
    Code both read hook stdout as UTF-8, so without this the hook output is
    corrupted on Windows. Likewise an incoming payload with accented text in
    ``tool_input`` must be read as UTF-8, not cp1252.
    """
    for stream in (sys.stdin, sys.stdout):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with suppress(ValueError, OSError):  # exotic/non-reconfigurable streams
                reconfigure(encoding="utf-8")


def _read_stdin() -> dict[str, Any] | None:
    try:
        raw = sys.stdin.read()
    except Exception:
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return cast(dict[str, Any], data)
    except json.JSONDecodeError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fscars.run_hook", add_help=True)
    parser.add_argument(
        "--adapter",
        default="claude_code",
        choices=sorted(_ADAPTERS),
        help="Which AI coding agent's hook payload to expect on stdin.",
    )
    args = parser.parse_args(argv)

    _force_utf8_io()

    raw = _read_stdin()
    if raw is None:
        # Cannot read or parse input — exit silently so we never break the host.
        sys.stdout.write("{}")
        return 0

    adapter_cls = _ADAPTERS[args.adapter]
    adapter = adapter_cls()
    payload = adapter.parse_stdin(raw)
    if payload is None:
        sys.stdout.write("{}")
        return 0

    # Discover the project's own scars (scaffolded by `fscar init`) rather than
    # the packaged cookbook catalog: scars are per-project and opt-in, and this
    # works in a plain `pip install` where `cookbook` is not importable.
    project_root = Path(payload.cwd) if payload.cwd else Path.cwd()
    registry = ScarRegistry.load_from_dir(default_store(project_root).scars_dir)
    result = engine.run(payload, registry=registry)
    sys.stdout.write(adapter.emit_output(result.output, payload))

    # PermissionRequest conveys a denial through the JSON decision object only.
    # Unlike PreToolUse / Stop / etc., the Codex docs do not document exit code 2
    # as a decision path for it, so a deny here returns 0 and relies on the
    # `decision: {"behavior": "deny"}` contract. See developers.openai.com/codex/hooks.
    if payload.event_type == HookEventType.PERMISSION_REQUEST:
        return 0
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
