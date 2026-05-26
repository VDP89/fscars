# Cookbook — import-aware hooks

A common failure mode for "fire when the file mentions X" hooks: the
substring matches everywhere it does not matter. The hook for "fire when a
Python edit imports library X" must not fire on:

* a test file that imports the library to *test integration with* X;
* a code-analysis script that mentions X in a comment;
* a tutorial-style file that shows X in a docstring;
* the hook script itself, which talks about X by name.

The v1 trap: substring matching on `"docx"` in any `.py` write. False
positive rate over the first 30 fires: **100%**. Every fire was a hook,
test, or analytics script that happened to spell the package name.

The fix is to look at the **import graph**, not the source text. `cookbook.
scars.import_aware_imports` ships a `FunctionalScar` subclass that does
this correctly.

## How it decides

```
file_path  ──▶  path filter  ──┐
                               │
content    ──▶  ast.parse  ────┼──▶  set of top-level imports
                  ↑            │
                  └─ syntax    │
                     error?    │       intersect with watched_packages
                  fallback to  │
                  regex scan   │             │
                               ▼             │
                                             ▼
                                  match  ◀── (or)
                                             ▲
                                             │
                              regex (usage_patterns) hits
                              AND path matches pipeline_path_fragments
```

1. **Path filter** — skip if not `.py`, or if any
   `exclude_path_fragments` substring matches. Defaults already cover
   tests, hooks, `__pycache__`, vendor dirs.
2. **AST parse** — `imported_top_level_packages(content)` walks
   `ast.parse(content)` and returns the set of top-level packages every
   `import` / `from ... import ...` pulls in. Relative imports
   (`from . import x`) are excluded — they never reference an external
   library.
3. **Regex fallback** — if `ast.parse` fails (in-progress edit with a
   syntax error), a line-based regex scans for `import x` / `from x.y
   import` so the hook still fires while the file is being written.
4. **Intersect** with `watched_packages`. Hit → fire.
5. **Optional usage path** — if no import matched but `usage_patterns`
   hit *and* the file path matches `pipeline_path_fragments`, fire
   anyway. Catches indirect imports like
   `importlib.import_module("docx")` inside known output directories.

## Minimal subclass

```python
from cookbook.scars.import_aware_imports import ImportAwareWriteScar

class DocxImportReminderScar(ImportAwareWriteScar):
    scar_id = "docx-import-reminder"
    name = "Remind to post-process DOCX outputs"
    rule = "Run the project's post-processing step before delivering."
    watched_packages = ("docx", "docxcompose")
    enabled = True
    reminder_context = (
        "[docx-import-reminder] Python edit imports docx. "
        "Run post-processing before delivering."
    )
    reminder_system_message = "docx-import-reminder: post-process before delivery"


scar = DocxImportReminderScar()
```

## With pipeline path heuristic

When the package is sometimes imported dynamically, raise sensitivity in a
known output area without firing globally:

```python
class DocxReminderScoped(ImportAwareWriteScar):
    scar_id = "docx-reminder-scoped"
    name = "Remind for DOCX builders in the reports tree"
    rule = "Run post-processing before delivering."
    watched_packages = ("docx",)
    pipeline_path_fragments = ("/reports/", "/informes/", "/generate_")
    usage_patterns = (
        r"\bDocument\s*\(",
        r"\.save\s*\(\s*['\"][^'\"]*\.docx['\"]",
    )
    enabled = True
```

Inside the listed directories the scar fires on `Document(...)` or
`.save("*.docx")` even without an `import docx` line. Outside, only a real
import triggers it.

## When NOT to use AST

* The scar should fire on *any text* mentioning a phrase — e.g.
  branding, profanity, security tokens. Substring matching is the right
  primitive there; AST adds nothing.
* The file type isn't Python. The current implementation only inspects
  `.py`. For TypeScript / Go / etc. you would want a different parser.
* You actually want to fire on `__import__("x")` dynamic loads and the
  loaded module is not statically declared — the AST scan misses that
  case. The `usage_patterns` + `pipeline_path_fragments` workaround
  helps but is heuristic, not exact.

## Testing the subclass

The cookbook ships unit tests at `tests/test_cookbook_import_aware.py`
covering AST detection, regex fallback, exclude paths, the usage-hint
escape hatch, and the example subclass. Copy that file as a starting
point — running it under `pytest tests/test_cookbook_import_aware.py -v`
should print one PASS per behaviour you care about.
