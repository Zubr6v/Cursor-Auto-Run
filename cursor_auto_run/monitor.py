"""Watch one scanner and invoke a button only after the policy says so."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from cursor_auto_run.decision import evaluate
from cursor_auto_run.models import Activity, ButtonHit, ScanReport
from cursor_auto_run.safety import RunMode


@dataclass
class MonitorConfig:
    enabled: bool = False
    paused: bool = False
    mode: RunMode = RunMode.SAFE
    delay_ms: int = 600
    custom_commands: list[str] = field(default_factory=list)
    extra_labels: list[str] = field(default_factory=list)


class Monitor:
    def __init__(self, scanner: object, clock=None, now_text=None) -> None:
        self.scanner = scanner
        self.clock = clock or time.monotonic
        self.now_text = now_text or _local_stamp
        self.pending: dict[str, tuple[float, str]] = {}
        self.cooldown_until: dict[str, float] = {}
        self._logged: set[str] = set()
        self._last_error: str | None = None
        self.click_count = 0

    def tick(self, config: MonitorConfig, force_log_scan: bool = False) -> tuple[list[Activity], ScanReport]:
        report = self.scanner.scan(  # type: ignore[attr-defined]
            extra_labels=list(config.extra_labels),
            custom_rules=list(config.custom_commands),
        )
        activities: list[Activity] = []
        if report.error and report.error != self._last_error:
            self._last_error = report.error
            activities.append(self._activity("error", "", "", report.error))
        elif not report.error:
            self._last_error = None

        if force_log_scan:
            activities.append(self._activity("scan", "", "", _scan_summary(report)))

        seen: set[str] = set()
        for button in report.buttons:
            seen.add(button.runtime_id)
            activities.extend(self._handle_button(button, config))

        for runtime_id in list(self.pending):
            if runtime_id not in seen:
                self.pending.pop(runtime_id, None)
        self._logged = {key for key in self._logged if key.split("|", 1)[0] in seen}
        stale = [key for key, until in self.cooldown_until.items() if until <= self.clock() and key not in seen]
        for key in stale:
            self.cooldown_until.pop(key, None)
        return activities, report

    def _handle_button(self, button: ButtonHit, config: MonitorConfig) -> list[Activity]:
        if not button.enabled:
            return self._once(button, "skipped", "кнопка недоступна")
        if button.offscreen:
            return self._once(button, "skipped", "кнопка поза видимою областю")

        decision = evaluate(
            button.name,
            button.context_text,
            config.mode,
            config.custom_commands,
            config.extra_labels,
        )
        if not decision.click:
            kind = "blocked" if decision.category in {
                "deletion",
                "disk",
                "admin",
                "system",
                "publish",
                "secrets",
                "remote",
                "scripts",
                "sandbox",
                "substitution",
            } else "skipped"
            return self._once(button, kind, decision.reason, decision.command)

        if not config.enabled:
            return []
        if config.paused:
            return self._once(button, "skipped", "пауза: кнопку не натиснуто", decision.command)

        now = self.clock()
        if self.cooldown_until.get(button.runtime_id, 0) > now:
            return []
        signature = f"{button.name}\n{button.context_text}"
        pending = self.pending.get(button.runtime_id)
        delay_s = max(0, min(5000, int(config.delay_ms))) / 1000
        if pending is None or pending[1] != signature:
            ready_at = now + delay_s
            self.pending[button.runtime_id] = (ready_at, signature)
            if delay_s > 0:
                return self._once(
                    button,
                    "scheduled",
                    f"натискання через {int(config.delay_ms)} мс, якщо команда не зміниться",
                    decision.command,
                )
        ready_at = self.pending[button.runtime_id][0]
        if now < ready_at:
            return []

        self.pending.pop(button.runtime_id, None)
        result = self.scanner.invoke(button.runtime_id)  # type: ignore[attr-defined]
        self.cooldown_until[button.runtime_id] = now + 3
        if not result.ok:
            return [self._activity("error", button.name, decision.command, result.detail)]
        self.click_count += 1
        return [self._activity("clicked", button.name, decision.command, result.detail)]

    def _once(self, button: ButtonHit, kind: str, reason: str, command: str = "") -> list[Activity]:
        key = f"{button.runtime_id}|{kind}|{reason}"
        if key in self._logged:
            return []
        self._logged.add(key)
        return [self._activity(kind, button.name, command, reason)]

    def _activity(self, kind: str, button: str, command: str, reason: str) -> Activity:
        return Activity(
            at=self.now_text(),
            kind=kind,
            button=button,
            command=command,
            reason=reason,
        )


def _scan_summary(report: ScanReport) -> str:
    blocked = ""
    if report.blocked_names:
        names = ", ".join(report.blocked_names[:6])
        blocked = f", відхилено назв: {len(report.blocked_names)} ({names})"
    note = f" Вікна Cursor: {report.cursor_windows}, кнопок підтвердження: {len(report.buttons)}{blocked}."
    if report.notes:
        note += " " + " ".join(report.notes)
    return note.strip()


def _local_stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")
