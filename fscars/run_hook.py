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

from fscars.adapters.base import Adapter
from fscars.adapters.claude_code import ClaudeCodeAdapter
from fscars.core import engine

_ADAPTERS: dict[str, type[Adapter]] = {
    "claude_code": ClaudeCodeAdapter,
}


def _read_stdin() -> dict | None:
    try:
        raw = sys.stdin.read()
    except Exception:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
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

    result = engine.run(payload)
    sys.stdout.write(adapter.emit_output(result.output))
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
