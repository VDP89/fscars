"""Tests for project-local scar discovery (`ScarRegistry.load_from_dir`).

This is the discovery path the hook entrypoint uses at runtime: it loads a
project's own `.fscars/scars/*.py` by file path, so it works in a plain
`pip install fscars` environment where the `cookbook` package is not importable.
"""

from __future__ import annotations

from pathlib import Path

from fscars.core.engine import ScarRegistry

_SCAR_SOURCE = '''\
from fscars.core.fire import Severity
from fscars.core.payload import HookEventType
from fscars.core.scar import FunctionalScar, ScarOutput


class ExampleScar(FunctionalScar):
    scar_id = "example-{tag}"
    name = "Example {tag}"
    rule = "example"
    severity = Severity.WARN
    event_type = HookEventType.USER_PROMPT_SUBMIT

    def matches(self, payload):
        return True

    def build_output(self, payload):
        return ScarOutput(additional_context="example")


scar = ExampleScar()
'''


def _write_scar(directory: Path, filename: str, tag: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(_SCAR_SOURCE.format(tag=tag), encoding="utf-8")


def test_load_from_dir_discovers_py_files(tmp_path: Path):
    scars_dir = tmp_path / "scars"
    _write_scar(scars_dir, "alpha.py", "alpha")
    _write_scar(scars_dir, "beta.py", "beta")

    registry = ScarRegistry.load_from_dir(scars_dir)

    ids = sorted(s.scar_id for s in registry.all())
    assert ids == ["example-alpha", "example-beta"]


def test_load_from_dir_skips_underscore_files(tmp_path: Path):
    scars_dir = tmp_path / "scars"
    _write_scar(scars_dir, "real.py", "real")
    _write_scar(scars_dir, "_template.py", "template")

    registry = ScarRegistry.load_from_dir(scars_dir)

    ids = [s.scar_id for s in registry.all()]
    assert ids == ["example-real"]


def test_load_from_dir_missing_dir_is_empty(tmp_path: Path):
    registry = ScarRegistry.load_from_dir(tmp_path / "does_not_exist")
    assert registry.all() == []


def test_load_from_dir_skips_unimportable_module(tmp_path: Path):
    scars_dir = tmp_path / "scars"
    _write_scar(scars_dir, "good.py", "good")
    (scars_dir / "broken.py").write_text("this is not valid python (", encoding="utf-8")

    registry = ScarRegistry.load_from_dir(scars_dir)

    # The broken module is skipped without breaking discovery of the good one.
    assert [s.scar_id for s in registry.all()] == ["example-good"]
