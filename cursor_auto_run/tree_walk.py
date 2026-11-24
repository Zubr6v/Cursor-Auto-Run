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
_CLICKABLE_TYPES = BUTTON_TYPES | {"CustomControl"}
_ACTION_TYPES = _CLICKABLE_TYPES | {"TextControl", "GroupControl", "PaneControl", "ListItemControl"}
_CARD_MARKERS = (
    "skip",
    "reject",
    "cancel",
    "deny",
    "allowlist",
    "allow list",
    "always run",
    "always allow",
    "dismiss",
)


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
            if control_type in _ACTION_TYPES:
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
    return _prefer(buttons), blocked, notes


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
        if name.strip() not in blocked:
            blocked.append(name.strip())
        return
    if not approved:
        return
    control_type = _control_type(node)
    if control_type not in _CLICKABLE_TYPES and _clickable_sibling(ancestors, text_of, extra_labels):
        return
    if not _in_approval_card(ancestors, text_of):
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


def _prefer(buttons: list[ButtonHit]) -> list[ButtonHit]:
    """Keep one Run button per card. Skip and Always Run never reach this list."""
    best: dict[str, ButtonHit] = {}
    for button in buttons:
        key = button.window_title + "\n" + button.context_text[:240]
        current = best.get(key)
        if current is None or _rank(button.name) < _rank(current.name):
            best[key] = button
    return list(best.values())


def _rank(name: str) -> int:
    label = normalize_label(name)
    if label in {"run", "run step"}:
        return 0
    if label.startswith("run "):
        return 1
    if label in {"allow", "allow once"} or label.startswith("allow once"):
        return 2
    return 3


def _clickable_sibling(ancestors: list[object], text_of: NodeText, extra_labels: list[str]) -> bool:
    if not ancestors:
        return False
    try:
        children = list(ancestors[0].GetChildren())  # type: ignore[attr-defined]
    except Exception:
        return False
    for child in children[:80]:
        if _control_type(child) not in _CLICKABLE_TYPES:
            continue
        label = text_of(child).split("\n", 1)[0]
        if is_approval_button(label, extra_labels)[0]:
            return True
    return False


def _in_approval_card(ancestors: list[object], text_of: NodeText) -> bool:
    """Run in the menu bar is not an approval. The card also shows Skip or Reject."""
    for ancestor in ancestors[:4]:
        try:
            children = list(ancestor.GetChildren())  # type: ignore[attr-defined]
        except Exception:
            continue
        if _children_have_marker(children, text_of):
            return True
    return False


def _children_have_marker(children: list[object], text_of: NodeText) -> bool:
    for child in children[:80]:
        label = normalize_label(text_of(child).split("\n", 1)[0])
        if any(marker in label for marker in _CARD_MARKERS):
            return True
        if _control_type(child) in {"GroupControl", "PaneControl", "CustomControl", "ToolBarControl"}:
            try:
                nested = list(child.GetChildren())  # type: ignore[attr-defined]
            except Exception:
                nested = []
            for item in nested[:40]:
                nested_label = normalize_label(text_of(item).split("\n", 1)[0])
                if any(marker in nested_label for marker in _CARD_MARKERS):
                    return True
    return False


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
