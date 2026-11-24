"""Per-user startup entry. This writes HKCU Run and does not request elevation."""

from __future__ import annotations

import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "CursorAutoRun"


def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return _quote(sys.executable) + " --minimized"
    return _quote(sys.executable) + " -m cursor_auto_run --minimized"


def set_autostart(enabled: bool, command: str | None = None) -> str | None:
    """Enable or remove the current-user Run value. Returns an error, if any."""
    if sys.platform != "win32":
        return "автозапуск доступний лише у Windows"
    import winreg

    command = command or launch_command()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
            else:
                _delete_value(winreg, key)
    except OSError as exc:
        return f"не вдалося змінити автозапуск: {exc}"
    return None


def autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
    except OSError:
        return False
    return True


def _delete_value(winreg_module: object, key: object) -> None:
    try:
        winreg_module.DeleteValue(key, VALUE_NAME)  # type: ignore[attr-defined]
    except FileNotFoundError:
        return
    except OSError as exc:
        if getattr(exc, "winerror", None) == 2:
            return
        raise


def _quote(path: str) -> str:
    if '"' in path:
        raise ValueError("шлях до програми містить лапки")
    return f'"{path}"'
