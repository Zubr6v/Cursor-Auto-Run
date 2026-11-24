"""Parse a hotkey and, on Windows, register it with RegisterHotKey.

The listener is a global toggle for this program. It does not send keys to Cursor.
"""

from __future__ import annotations

import ctypes
import re
import sys
import threading
from ctypes import wintypes

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001

_SPECIAL_KEYS = {
    "space": 0x20,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "enter": 0x0D,
    "return": 0x0D,
    "pause": 0x13,
}


def parse_hotkey(text: str) -> tuple[int, int] | None:
    """Return (modifiers, virtual_key). A modifier is required."""
    parts = [part.strip() for part in (text or "").split("+") if part.strip()]
    if len(parts) < 2:
        return None
    modifiers = MOD_NOREPEAT
    key: str | None = None
    for part in parts:
        lowered = part.lower()
        if lowered in {"ctrl", "control"}:
            modifiers |= MOD_CONTROL
        elif lowered == "alt":
            modifiers |= MOD_ALT
        elif lowered == "shift":
            modifiers |= MOD_SHIFT
        elif lowered in {"win", "meta", "super"}:
            modifiers |= MOD_WIN
        elif key is None:
            key = part
        else:
            return None
    if key is None or modifiers == MOD_NOREPEAT:
        return None
    virtual_key = _virtual_key(key)
    if virtual_key is None:
        return None
    return modifiers, virtual_key


class GlobalHotkey:
    """Background RegisterHotKey loop. start() is a no-op off Windows."""

    def __init__(self, callback) -> None:
        self._callback = callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._hotkey_id = 1

    def start(self, sequence: str) -> str | None:
        self.stop()
        parsed = parse_hotkey(sequence)
        if parsed is None:
            return "комбінація має містити модифікатор і клавішу, наприклад Ctrl+Alt+A"
        if sys.platform != "win32":
            return None
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            args=parsed,
            name="cursor-auto-run-hotkey",
            daemon=True,
        )
        self._thread.start()
        return None

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=1.0)
        self._thread = None

    def _loop(self, modifiers: int, virtual_key: int) -> None:
        user32 = ctypes.windll.user32
        user32.RegisterHotKey.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.UnregisterHotKey.restype = wintypes.BOOL
        user32.PeekMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
        ]
        user32.PeekMessageW.restype = wintypes.BOOL
        if not user32.RegisterHotKey(None, self._hotkey_id, modifiers, virtual_key):
            return
        message = wintypes.MSG()
        try:
            while not self._stop.is_set():
                while user32.PeekMessageW(
                    ctypes.byref(message),
                    None,
                    0,
                    0,
                    PM_REMOVE,
                ):
                    if message.message == WM_HOTKEY and message.wParam == self._hotkey_id:
                        self._callback()
                self._stop.wait(0.05)
        finally:
            user32.UnregisterHotKey(None, self._hotkey_id)


def _virtual_key(key: str) -> int | None:
    if len(key) == 1 and key.isalpha():
        return ord(key.upper())
    if len(key) == 1 and key.isdigit():
        return ord(key)
    match = re.fullmatch(r"F(\d{1,2})", key, re.IGNORECASE)
    if match:
        number = int(match.group(1))
        if 1 <= number <= 24:
            return 0x70 + number - 1
    return _SPECIAL_KEYS.get(key.lower())
