"""Find Cursor.exe windows and invoke an approval button with InvokePattern.

This uses Microsoft UI Automation, the same API a screen reader uses.
It does not send mouse or keyboard input, does not attach a debugger, and
does not talk to any Cursor-private or Chrome DevTools endpoint.
"""

from __future__ import annotations

import ctypes
import re
import sys
from ctypes import wintypes

from cursor_auto_run.models import InvokeResult, ScanReport
from cursor_auto_run.tree_walk import collect_buttons

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
CURSOR_EXECUTABLE = "cursor.exe"


def is_cursor_executable(path: str) -> bool:
    name = re.split(r"[\\/]", path or "")[-1]
    return name.lower() == CURSOR_EXECUTABLE


class WindowsCursorScanner:
    def __init__(self) -> None:
        self._auto = None
        self._live: dict[str, object] = {}
        self._names: dict[int, str] = {}

    def prepare(self) -> None:
        if sys.platform != "win32":
            raise OSError("UI Automation доступна лише у Windows")
        import uiautomation as auto

        auto.InitializeUIAutomationInCurrentThread()
        auto.SetGlobalSearchTimeout(0.2)
        self._auto = auto

    def close(self) -> None:
        self._live.clear()
        auto = self._auto
        self._auto = None
        if auto is not None:
            auto.UninitializeUIAutomationInCurrentThread()

    def scan(
        self,
        extra_labels: list[str] | None = None,
        custom_rules: list[str] | None = None,
    ) -> ScanReport:
        if self._auto is None:
            self.prepare()
        auto = self._auto
        assert auto is not None
        self._live = {}
        buttons = []
        blocked: list[str] = []
        notes: list[str] = []
        windows = 0
        try:
            roots = auto.GetRootControl().GetChildren()
        except Exception as exc:
            return ScanReport(error=f"не вдалося прочитати дерево UI Automation: {exc}")
        for window in roots:
            try:
                pid = int(window.ProcessId)
            except Exception:
                continue
            image = self._process_name(pid)
            if not is_cursor_executable(image):
                continue
            windows += 1
            try:
                title = window.Name or ""
            except Exception:
                title = ""

            def remember(hit, node, _scanner=self) -> None:
                _scanner._live[hit.runtime_id] = node

            found, blocked_names, walk_notes = collect_buttons(
                window,
                window_title=title,
                extra_labels=extra_labels,
                custom_rules=custom_rules,
                node_text=lambda node: _uia_text(auto, node),
                on_button=remember,
            )
            buttons.extend(found)
            blocked.extend(blocked_names)
            notes.extend(walk_notes)
        if windows == 0:
            notes.append("вікно Cursor.exe не знайдено")
        if windows and not buttons and not blocked:
            notes.append(
                "кнопок Run, Allow, Continue або Allow once в дереві доступності не видно. "
                "Cursor має показати їх зчитувачу екрана; інакше підтвердіть команду вручну."
            )
        return ScanReport(
            cursor_windows=windows,
            buttons=buttons,
            blocked_names=blocked,
            notes=notes,
        )

    def invoke(self, runtime_id: str) -> InvokeResult:
        control = self._live.get(runtime_id)
        if control is None:
            return InvokeResult(False, "кнопка вже зникла, Invoke не викликано")
        invoked = _try_invoke(control)
        if invoked is None:
            return InvokeResult(True, "InvokePattern.Invoke")
        legacy = _try_legacy(control)
        if legacy is None:
            return InvokeResult(True, "LegacyIAccessible.DoDefaultAction")
        clicked = _try_element_click(control)
        if clicked is None:
            return InvokeResult(True, "клацання по знайденій кнопці Run")
        return InvokeResult(False, invoked)

    def _process_name(self, pid: int) -> str:
        cached = self._names.get(pid)
        if cached is not None:
            return cached
        name = _query_process_image(pid)
        self._names[pid] = name
        return name


def _try_invoke(control: object) -> str | None:
    try:
        pattern = control.GetInvokePattern()  # type: ignore[attr-defined]
    except Exception as exc:
        return f"InvokePattern недоступний: {exc}"
    if pattern is None:
        return "у кнопки немає InvokePattern"
    try:
        ok = bool(pattern.Invoke(waitTime=0))
    except Exception as exc:
        return f"Invoke завершився помилкою: {exc}"
    if not ok:
        return "Invoke повернув помилку, кнопку не натиснуто"
    return None


def _try_legacy(control: object) -> str | None:
    getter = getattr(control, "GetLegacyIAccessiblePattern", None)
    if getter is None:
        return "LegacyIAccessible недоступний"
    try:
        pattern = getter()
    except Exception as exc:
        return f"LegacyIAccessible недоступний: {exc}"
    if pattern is None:
        return "у кнопки немає LegacyIAccessible"
    try:
        ok = bool(pattern.DoDefaultAction(waitTime=0))
    except Exception as exc:
        return f"DoDefaultAction завершився помилкою: {exc}"
    if not ok:
        return "DoDefaultAction повернув помилку"
    return None


def _try_element_click(control: object) -> str | None:
    """Click that element only. No key is sent to the Cursor window."""
    click = getattr(control, "Click", None)
    if click is None:
        return "кнопка не має методу Click"
    try:
        click(simulateMove=False, waitTime=0)
    except Exception as exc:
        return f"клацання по кнопці не вдалося: {exc}"
    return None


def _query_process_image(pid: int) -> str:
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def _uia_text(auto, control: object) -> str:
    try:
        name = (control.Name or "").strip()  # type: ignore[attr-defined]
    except Exception:
        name = ""
    parts = [name] if name else []
    try:
        control_type = control.ControlTypeName  # type: ignore[attr-defined]
    except Exception:
        control_type = ""
    if control_type in {"EditControl", "DocumentControl"}:
        try:
            pattern = control.GetPattern(auto.PatternId.ValuePattern)  # type: ignore[attr-defined]
            value = (pattern.Value or "").strip() if pattern is not None else ""
        except Exception:
            value = ""
        if value and value not in name:
            parts.append(value[:400])
    return "\n".join(parts)
