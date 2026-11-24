"""Decide whether one visible Cursor button may be invoked."""

from __future__ import annotations

from cursor_auto_run.models import ClickDecision
from cursor_auto_run.safety import (
    MAX_COMMANDS,
    MAX_CONTEXT_CHARS,
    RunMode,
    classify_command,
    context_is_unsandboxed,
    extract_commands,
    is_approval_button,
    redact,
)


def evaluate(
    button_name: str,
    context: str,
    mode: RunMode | str,
    custom_rules: list[str] | None = None,
    extra_labels: list[str] | None = None,
) -> ClickDecision:
    rules = list(custom_rules or [])
    selected = RunMode.parse(mode)
    approved, reason = is_approval_button(button_name, extra_labels)
    if not approved:
        return ClickDecision(False, reason, "", "button")
    if selected is RunMode.MANUAL:
        return ClickDecision(
            False,
            "ручний режим: автоматичне натискання вимкнено",
            "",
            "manual",
        )
    if context_is_unsandboxed(button_name, context):
        return ClickDecision(
            False,
            "запуск поза пісочницею потребує ручного підтвердження",
            "",
            "sandbox",
        )
    if len(context or "") > MAX_CONTEXT_CHARS:
        return ClickDecision(
            False,
            "контекст кнопки занадто широкий, команду не відділено від решти вікна",
            "",
            "context",
        )
    commands = extract_commands(context, rules)
    if not commands:
        return ClickDecision(
            False,
            "текст команди не знайдено, кнопку не натиснуто",
            "",
            "context",
        )
    if len(commands) > MAX_COMMANDS:
        return ClickDecision(
            False,
            "у контексті кілька команд, потрібне ручне підтвердження",
            redact(commands[0]),
            "context",
        )

    levels: list[str] = []
    shown: list[str] = []
    for command in commands:
        verdict = classify_command(command, rules)
        safe_command = redact(command)
        if verdict.outcome == "deny":
            return ClickDecision(False, verdict.reason, safe_command, verdict.category)
        if verdict.outcome != "allow":
            return ClickDecision(False, verdict.reason, safe_command, verdict.category)
        levels.append(verdict.level)
        shown.append(safe_command)

    if selected is RunMode.SAFE and any(level != "safe" for level in levels):
        return ClickDecision(
            False,
            "у безпечному режимі дозволені лише читання, тести і локальна збірка",
            shown[0],
            "mode",
        )
    return ClickDecision(True, "команда дозволена правилами", " && ".join(shown), "allowed")
