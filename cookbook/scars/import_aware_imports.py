"""Starter scar — fire only when a Python edit *actually* imports a target package.

This is the AST-based generalisation of an old DG production trap: a v1 hook
that matched any ``.py`` file mentioning the package name as a string fired
on **every** read of an analytics script, hook, or test that merely talked
about the library. False positive rate: 100% over 30 fires.

The fix is to look at the import graph instead of doing substring matching:

1. **Path filter** — only ``.py`` files outside obvious noise paths (tests,
   hooks, ``__pycache__``, vendor dirs).
2. **AST parse** — when the content is valid Python, walk ``ast.parse`` and
   list every top-level package the file pulls in.
3. **Regex fallback** — for syntactically invalid in-progress edits, scan
   ``import``/``from`` lines so half-written code still triggers.
4. **Match against ``watched_packages``** — fire only if at least one is
   imported.

Optional ``pipeline_path_fragments`` + ``usage_patterns`` raise sensitivity
in a known-output area (e.g. report generation directory) by matching on
*usage hints* such as constructor calls or output file extensions, even when
the import is indirect (``importlib.import_module``, dynamic dispatch).

Customise the class attributes and export ``scar = YourScar()`` to plug it
into the registry. The example at the bottom of this file is disabled by
default.
"""

from __future__ import annotations

import ast
import re
from typing import ClassVar

from fscars.core.fire import Severity
from fscars.core.payload import HookEventType, HookPayload
from fscars.core.scar import FunctionalScar, ScarOutput

DEFAULT_EXCLUDE_FRAGMENTS: tuple[str, ...] = (
    "test_",
    "_test.py",
    "smoke_",
    "_smoke",
    "/hook_",
    "\\hook_",
    "__pycache__",
    "/conftest.py",
    "\\conftest.py",
    "/node_modules/",
    "/.venv/",
    "\\.venv\\",
    "/dist/",
    "/build/",
)


def imported_top_level_packages(content: str) -> set[str]:
    """Return the set of top-level package names imported by ``content``.

    Prefers ``ast`` for accuracy; falls back to a regex scan when ``content``
    is not syntactically valid Python (common during in-progress edits).
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return _regex_imports(content)

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    found.add(alias.name.split(".", 1)[0])
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0
        ):
            found.add(node.module.split(".", 1)[0])
    return found


_REGEX_IMPORT = re.compile(
    r"^\s*(?:from\s+([\w][\w.]*)\s+import\b|import\s+([\w][\w.]*)\b)",
    re.MULTILINE,
)


def _regex_imports(content: str) -> set[str]:
    out: set[str] = set()
    for from_pkg, import_pkg in _REGEX_IMPORT.findall(content):
        pkg = from_pkg or import_pkg
        if pkg:
            out.add(pkg.split(".", 1)[0])
    return out


class ImportAwareWriteScar(FunctionalScar):
    """Subclass and set ``watched_packages`` + reminder text.

    A subclass minimally needs to override ``scar_id``, ``name``, ``rule``,
    ``watched_packages``, and (optionally) ``reminder_context`` /
    ``reminder_system_message``. Everything else has a sensible default.
    """

    severity = Severity.WARN
    event_type = HookEventType.PRE_TOOL_USE
    tool_matchers = ("Write", "Edit")
    enabled = False  # subclasses opt in

    # Detection knobs
    watched_packages: ClassVar[tuple[str, ...]] = ()
    exclude_path_fragments: ClassVar[tuple[str, ...]] = DEFAULT_EXCLUDE_FRAGMENTS
    pipeline_path_fragments: ClassVar[tuple[str, ...]] = ()
    usage_patterns: ClassVar[tuple[str, ...]] = ()

    # Surface text
    reminder_context: ClassVar[str] = ""
    reminder_system_message: ClassVar[str] = ""

    # ----- detection --------------------------------------------------

    def _path_is_excluded(self, file_path: str) -> bool:
        return any(frag in file_path for frag in self.exclude_path_fragments)

    def _path_is_pipeline(self, file_path: str) -> bool:
        return bool(self.pipeline_path_fragments) and any(
            frag in file_path for frag in self.pipeline_path_fragments
        )

    def _has_usage_hint(self, content: str) -> bool:
        return any(re.search(p, content) for p in self.usage_patterns)

    def matches(self, payload: HookPayload) -> bool:
        if not self.watched_packages:
            return False
        file_path = (payload.file_path or "").lower()
        if not file_path.endswith(".py"):
            return False
        if self._path_is_excluded(file_path):
            return False

        content = payload.content or ""
        imports = imported_top_level_packages(content)
        if imports & set(self.watched_packages):
            return True

        return self._has_usage_hint(content) and self._path_is_pipeline(file_path)

    # ----- output -----------------------------------------------------

    def build_output(self, payload: HookPayload) -> ScarOutput:
        return ScarOutput(
            additional_context=self.reminder_context
            or f"[{self.scar_id}] {self.rule}",
            system_message=self.reminder_system_message
            or f"{self.scar_id} active",
        )

    def trigger_match(self, payload: HookPayload) -> str:
        file_path = (payload.file_path or "").lower()
        content = payload.content or ""
        imports = imported_top_level_packages(content)
        watched_hit = sorted(imports & set(self.watched_packages))
        base = (payload.file_path or "").rsplit("/", 1)[-1]
        if watched_hit:
            return f"{base} — import:{','.join(watched_hit)}"
        if self._has_usage_hint(content) and self._path_is_pipeline(file_path):
            return f"{base} — usage_hint+pipeline_path"
        return base


# ---------------------------------------------------------------------------
# Example subclass — disabled. Uncomment ``scar = ...`` at the bottom and edit
# ``watched_packages`` to match the library you actually want to track.
# ---------------------------------------------------------------------------


class DocxImportReminderScar(ImportAwareWriteScar):
    """Example: remind the operator to post-process ``.docx`` outputs.

    Fires when a Python edit imports ``docx`` or ``docxcompose`` (or shows
    usage hints inside a known report pipeline directory).
    """

    scar_id = "docx-import-reminder"
    name = "Remind to post-process DOCX outputs"
    rule = (
        "After writing a script that builds DOCX files, remember to run any "
        "post-processing the project relies on (encoding fixes, header "
        "stamping, accent normalisation, etc.)."
    )
    watched_packages = ("docx", "docxcompose")
    pipeline_path_fragments = ("/reports/", "/informes/", "/generate_")
    usage_patterns = (
        r"\bDocument\s*\(",
        r"\.save\s*\(\s*['\"][^'\"]*\.docx['\"]",
    )
    reminder_context = (
        "[docx-import-reminder] Python edit imports docx. Remember to run "
        "the project's post-processing step before delivering the file."
    )
    reminder_system_message = "docx-import-reminder: post-process before delivery"


# scar = DocxImportReminderScar()  # uncomment to register
