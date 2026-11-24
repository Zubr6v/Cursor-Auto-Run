"""Scanner factory. The Windows implementation is imported only on Windows."""

from __future__ import annotations

import sys

from cursor_auto_run.models import InvokeResult, ScanReport


class UnavailableScanner:
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def prepare(self) -> None:
        return None

    def close(self) -> None:
        return None

    def scan(self, extra_labels: list[str] | None = None, custom_rules: list[str] | None = None) -> ScanReport:
        del extra_labels, custom_rules
        return ScanReport(cursor_windows=0, notes=[self.reason], error=self.reason)

    def invoke(self, runtime_id: str) -> InvokeResult:
        del runtime_id
        return InvokeResult(False, self.reason)


def default_scanner() -> object:
    if sys.platform != "win32":
        return UnavailableScanner(
            "UI Automation доступна лише у Windows. Правила команд працюють, "
            "але кнопки Cursor з цієї системи не натискаються."
        )
    from cursor_auto_run.win_scanner import WindowsCursorScanner

    return WindowsCursorScanner()
