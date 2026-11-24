"""Walk a UI Automation-like tree and keep only approval buttons.

The walker is pure: tests feed it plain objects with the same attributes the
Windows scanner reads from uiautomation. It never clicks.
"""

from __future__ import annotations

from collections.abc import Callable

from cursor_auto_run.models import ButtonHit
from cursor_auto_run.safety import (
    MAX_CONTEXT_CHARS,
    extract_commands,
    is_approval_button,
    normalize_label,
)

NodeText = Callable[[object], str]
BUTTON_TYPES = frozenset({"ButtonControl", "SplitButtonControl", "HyperlinkControl"})


def choose_context(levels_near_to_far: list[str], custom_rules: list[str] | None = None) -> str:
    """Use the nearest small container that already holds a command line."""
    best = ""
    for blob in levels_near_to_far:
        text = (blob or "").strip()
        if not text:
            continue
        if len(text) > MAX_CONTEXT_CHARS:
            return best
        best = text
        if extract_commands(text, custom_rules):
            return text
    return best


def collect_buttons(
    window: object,
    *,
    window_title: str,
    extra_labels: list[str] | None = None,
    custom_rules: list[str] | None = None,
    node_text: NodeText | None = None,
    on_button: Callable[[ButtonHit, object], None] | None = None,
    max_depth: int = 18,
    max_nodes: int = 5000,
) -> tuple[list[ButtonHit], list[str], list[str]]:
    """Return approval buttons, blocked button names, and scan notes."""
    text_of = node_text or _default_text
    labels = list(extra_labels or [])
    rules = list(custom_rules or [])
    buttons: list[ButtonHit] = []
    blocked: list[str] = []
    notes: list[str] = []
    seen_nodes = 0
    truncated = False

    def walk(node: object, ancestors: list[object], depth: int) -> None:
        nonlocal seen_nodes, truncated
        if truncated or depth > max_depth:
            return
        try:
            children = list(node.GetChildren())  # type: ignore[attr-defined]
        except Exception:
            return
        for child in children:
            seen_nodes += 1
            if seen_nodes > max_nodes:
                truncated = True
                return
            control_type = _control_type(child)
            if control_type in BUTTON_TYPES:
                _consider(
                    child,
                    ancestors,
                    text_of,
                    labels,
                    rules,
                    window_title,
                    buttons,
                    blocked,
                    on_button,
                )
            walk(child, [child, *ancestors], depth + 1)

    walk(window, [], 0)
    if truncated:
        notes.append("обхід дерева зупинено: забагато елементів")
    return buttons, blocked, notes


def _consider(
    node: object,
    ancestors: list[object],
    text_of: NodeText,
    extra_labels: list[str],
    custom_rules: list[str],
    window_title: str,
    buttons: list[ButtonHit],
    blocked: list[str],
    on_button: Callable[[ButtonHit, object], None] | None,
) -> None:
    name = text_of(node).split("\n", 1)[0].strip()
    if not name:
        return
    approved, blocked_reason = is_approval_button(name, extra_labels)
    if not approved and blocked_reason.startswith("кнопку"):
        blocked.append(name.strip())
        return
    if not approved:
        return
    levels: list[str] = []
    for ancestor in ancestors[:5]:
        try:
            children = list(ancestor.GetChildren())  # type: ignore[attr-defined]
        except Exception:
            children = []
        chunks = [text_of(child).strip() for child in children[:40]]
        levels.append("\n".join(chunk[:400] for chunk in chunks if chunk))
    context = choose_context(levels, custom_rules)
    buttons.append(
        ButtonHit(
            name=name,
            runtime_id=_runtime_id(node, name, context),
            context_text=context,
            enabled=_flag(node, "IsEnabled", True),
            offscreen=_flag(node, "IsOffscreen", False),
            window_title=window_title,
        )
    )
    if on_button is not None:
        on_button(buttons[-1], node)


def _default_text(node: object) -> str:
    name = str(getattr(node, "Name", "") or "").strip()
    value = str(getattr(node, "Value", "") or "").strip()
    if value and value not in name:
        return f"{name}\n{value}".strip()
    return name


def _control_type(node: object) -> str:
    try:
        return str(getattr(node, "ControlTypeName", "") or "")
    except Exception:
        return ""


def _flag(node: object, attr: str, default: bool) -> bool:
    try:
        return bool(getattr(node, attr))
    except Exception:
        return default


def _runtime_id(node: object, name: str, context: str) -> str:
    getter = getattr(node, "GetRuntimeId", None)
    if getter is not None:
        try:
            value = getter()
            parts = [str(int(part)) for part in value]
            if parts:
                return ".".join(parts)
        except Exception:
            pass
    return f"fallback:{normalize_label(name)}:{normalize_label(context)[:80]}"
