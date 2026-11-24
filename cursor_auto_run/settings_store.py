"""JSON settings in the user profile. Nothing here is sent off the machine."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cursor_auto_run.safety import RunMode


def app_directory() -> Path:
    if os.name == "nt":
        root = os.environ.get("APPDATA") or str(Path.home())
        return Path(root) / "CursorAutoRun"
    return Path.home() / ".config" / "cursor-auto-run"


@dataclass
class Settings:
    auto_run: bool = False
    paused: bool = False
    mode: str = RunMode.SAFE.value
    delay_ms: int = 600
    start_with_windows: bool = False
    restore_on_startup: bool = True
    hotkey: str = "Ctrl+Alt+A"
    custom_commands: list[str] = field(default_factory=list)
    extra_labels: list[str] = field(default_factory=list)
    click_count: int = 0

    def cleaned(self) -> "Settings":
        try:
            delay = int(self.delay_ms)
        except (TypeError, ValueError):
            delay = 600
        try:
            clicks = int(self.click_count)
        except (TypeError, ValueError):
            clicks = 0
        return Settings(
            auto_run=bool(self.auto_run),
            paused=bool(self.paused),
            mode=RunMode.parse(self.mode).value,
            delay_ms=max(0, min(5000, delay)),
            start_with_windows=bool(self.start_with_windows),
            restore_on_startup=bool(self.restore_on_startup),
            hotkey=(self.hotkey or "Ctrl+Alt+A").strip() or "Ctrl+Alt+A",
            custom_commands=_lines(self.custom_commands),
            extra_labels=_lines(self.extra_labels),
            click_count=max(0, clicks),
        )


def load_settings(path: Path | None = None) -> Settings:
    target = path or (app_directory() / "settings.json")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return Settings()
    if not isinstance(payload, dict):
        return Settings()
    known = {name: payload.get(name, getattr(Settings(), name)) for name in Settings.__dataclass_fields__}
    try:
        return Settings(**known).cleaned()
    except TypeError:
        return Settings()


def save_settings(settings: Settings, path: Path | None = None) -> Path:
    target = path or (app_directory() / "settings.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(settings.cleaned())
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _lines(value: object) -> list[str]:
    if isinstance(value, str):
        items = value.splitlines()
    elif isinstance(value, list):
        items = [str(item) for item in value]
    else:
        items = []
    cleaned = [item.strip() for item in items if str(item).strip()]
    return cleaned[:100]
