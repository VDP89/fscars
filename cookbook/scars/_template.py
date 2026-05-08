"""Template — copy this file to start a new starter scar.

After copy:
1. Rename the file to `<your_slug>.py` (snake_case).
2. Set scar_id, name, rule, severity, event_type and matchers.
3. Implement `matches` and `build_output`.
4. Export `scar = YourScar()` at module bottom so the registry picks it up.
5. Add a unit test under `tests/cookbook/test_<your_slug>.py`.
"""

from __future__ import annotations

from fscars.core.fire import Severity
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import FunctionalScar, ScarOutput


class TemplateScar(FunctionalScar):
    scar_id = "template-scar"
    name = "Replace me"
    rule = "Replace with the binary rule the scar enforces."
    severity = Severity.WARN
    event_type = HookEventType.PRE_TOOL_USE
    tool_matchers = ("Write", "Edit")
    enabled = False  # disabled by default so the template never fires

    def matches(self, payload: HookPayload) -> bool:
        return False

    def build_output(self, payload: HookPayload) -> ScarOutput:
        return ScarOutput()


# Do NOT export `scar` here — the template should not register itself.
