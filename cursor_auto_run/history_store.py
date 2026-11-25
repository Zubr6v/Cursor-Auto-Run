"""Append-only local history of decisions. Command text is redacted first."""

from __future__ import annotations

import json
from pathlib import Path

from cursor_auto_run.models import Activity
from cursor_auto_run.settings_store import app_directory


def history_path(path: Path | None = None) -> Path:
    return path or (app_directory() / "history.jsonl")


def load_history(path: Path | None = None, limit: int = 300) -> list[Activity]:
    target = history_path(path)
    if not target.exists():
        return []
    rows: list[Activity] = []
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return []
    for line in lines[-limit:]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(Activity.from_dict(payload))
    return rows


def append_history(activity: Activity, path: Path | None = None, limit: int = 300) -> None:
    target = history_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(activity.to_dict(), ensure_ascii=False) + "\n")
    _trim(target, limit)


def _trim(path: Path, limit: int) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) <= limit:
        return
    path.write_text("\n".join(lines[-limit:]) + "\n", encoding="utf-8")
