"""Starter scar — require explicit UTF-8 encoding in pandas.read_csv calls.

Common data-science correction: the model defaults to no-encoding, then
breaks on UTF-8-BOM files. Explicit `encoding="utf-8"` prevents the loop.
"""

from __future__ import annotations

import re

from fscars.core.fire import Severity
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import FunctionalScar, ScarOutput

READ_CSV_PATTERN = re.compile(
    r"\bpd\.read_csv\s*\([^)]*\)|\bread_csv\s*\([^)]*\)",
    re.DOTALL,
)
ENCODING_PATTERN = re.compile(r"\bencoding\s*=")


class CsvEncodingScar(FunctionalScar):
    scar_id = "csv-encoding"
    name = "pandas.read_csv requires explicit encoding"
    rule = (
        "Every pandas.read_csv call must pass encoding='utf-8' (or a "
        "deliberate alternative). Implicit defaults break on UTF-8-BOM "
        "files and the failure mode is silent corruption."
    )
    severity = Severity.WARN
    event_type = HookEventType.PRE_TOOL_USE
    tool_matchers = ("Write", "Edit")

    def matches(self, payload: HookPayload) -> bool:
        if not payload.file_path.endswith((".py", ".ipynb")):
            return False
        content = payload.content
        for m in READ_CSV_PATTERN.finditer(content):
            if not ENCODING_PATTERN.search(m.group(0)):
                return True
        return False

    def build_output(self, payload: HookPayload) -> ScarOutput:
        return ScarOutput(
            additional_context=(
                f"[{self.scar_id}] read_csv call without explicit encoding. "
                f"{self.rule}"
            ),
            system_message=f"{self.scar_id}: add encoding='utf-8' before saving",
        )


scar = CsvEncodingScar()
