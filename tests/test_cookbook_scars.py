"""Smoke tests for the cookbook starter scars."""

from __future__ import annotations

from cookbook.scars.avoid_negative_framing import scar as nfs_scar
from cookbook.scars.csv_encoding import scar as csv_scar
from cookbook.scars.large_write_review import scar as large_scar
from cookbook.scars.subagent_coverage_report import scar as subagent_scar
from cookbook.scars.utc_timestamps import scar as utc_scar
from fscars.core.payload import HookEventType

# ---------- large_write_review ----------------------------------------------


def test_large_write_review_triggers_above_threshold(payload_factory):
    body = "\n".join(["line"] * 250)
    p = payload_factory(tool_input={"file_path": "src/x.py", "content": body})
    assert large_scar.matches(p) is True


def test_large_write_review_skips_short_writes(payload_factory):
    p = payload_factory(tool_input={"file_path": "src/x.py", "content": "tiny"})
    assert large_scar.matches(p) is False


def test_large_write_review_skips_non_code(payload_factory):
    body = "\n".join(["line"] * 250)
    p = payload_factory(tool_input={"file_path": "docs/x.md", "content": body})
    assert large_scar.matches(p) is False


# ---------- utc_timestamps --------------------------------------------------


def test_utc_timestamps_triggers_in_handler(payload_factory):
    p = payload_factory(
        tool_input={
            "file_path": "src/handler.go",
            "content": "now := time.Now()\n",
        }
    )
    assert utc_scar.matches(p) is True


def test_utc_timestamps_skips_non_handler_files(payload_factory):
    p = payload_factory(
        tool_input={
            "file_path": "src/utils.go",
            "content": "now := time.Now()\n",
        }
    )
    assert utc_scar.matches(p) is False


# ---------- csv_encoding -----------------------------------------------------


def test_csv_encoding_triggers_without_kwarg(payload_factory):
    p = payload_factory(
        tool_input={
            "file_path": "src/load.py",
            "content": "df = pd.read_csv('foo.csv')",
        }
    )
    assert csv_scar.matches(p) is True


def test_csv_encoding_passes_with_explicit_encoding(payload_factory):
    p = payload_factory(
        tool_input={
            "file_path": "src/load.py",
            "content": "df = pd.read_csv('foo.csv', encoding='utf-8')",
        }
    )
    assert csv_scar.matches(p) is False


# ---------- avoid_negative_framing ------------------------------------------


def test_avoid_negative_framing_triggers_on_marketing_md(payload_factory):
    p = payload_factory(
        tool_input={
            "file_path": "site/brand-page.md",
            "content": "We are not just a tool. We don't do that.",
        }
    )
    assert nfs_scar.matches(p) is True


def test_avoid_negative_framing_skips_non_marketing(payload_factory):
    p = payload_factory(
        tool_input={
            "file_path": "src/utils.py",
            "content": "We are not just a tool",
        }
    )
    assert nfs_scar.matches(p) is False


# ---------- subagent_coverage_report ----------------------------------------


def test_subagent_coverage_only_fires_on_task_tool(payload_factory):
    p_match = payload_factory(
        event_type=HookEventType.PRE_TOOL_USE,
        tool_name="Task",
        tool_input={"prompt": "..."},
    )
    p_skip = payload_factory(tool_name="Write")

    assert subagent_scar.matches(p_match) is True
    assert subagent_scar.matches(p_skip) is False
