"""Walk a UI Automation-like tree and keep only approval buttons.

The walker is pure: tests feed it plain objects with the same attributes the
Windows scanner reads from uiautomation. It never clicks.
"""

from __future__ import annotations

import re
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
_CLICKABLE_TYPES = BUTTON_TYPES | {"CustomControl", "ImageControl", "DataItemControl", "ListItemControl"}
_IGNORE_TYPES = frozenset(
    {
        "MenuItemControl",
        "MenuControl",
        "MenuBarControl",
        "TitleBarControl",
        "ScrollBarControl",
        "ThumbControl",
        "ToolTipControl",
        "WindowControl",
        "StatusBarControl",
        "SeparatorControl",
        "ProgressBarControl",
    }
)
_NOT_RUN_WORDS = ("stop", "copy", "edit", "undo", "retry", "pause", "close", "show more")
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
    max_depth: int = 24,
    max_nodes: int = 15000,
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
            if control_type not in _IGNORE_TYPES:
                _consider(
                    child,
                    ancestors,
                    text_of,
                    labels,
                    rules,
                    window_title,
                    buttons,
                    blocked,
                    notes,
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
    notes: list[str],
    on_button: Callable[[ButtonHit, object], None] | None,
) -> None:
    name = _visible_label(node, text_of)
    if not name or (len(name) > 120 and not normalize_label(name).startswith("run")):
        return
    approved, blocked_reason = is_approval_button(name, extra_labels)
    if not approved and blocked_reason.startswith("кнопку"):
        if name.strip() not in blocked:
            blocked.append(name.strip())
        if _is_skip_label(name):
            _take_run_sibling(
                node,
                ancestors,
                text_of,
                extra_labels,
                custom_rules,
                window_title,
                buttons,
                notes,
                on_button,
            )
        return
    if not approved:
        return
    control_type = _control_type(node)
    if control_type not in _CLICKABLE_TYPES and _clickable_sibling(ancestors, text_of, extra_labels):
        return
    if control_type not in _CLICKABLE_TYPES and ancestors and _control_type(ancestors[0]) in _CLICKABLE_TYPES:
        return
    if not _in_approval_card(ancestors, text_of):
        return
    _add_button(
        node,
        name,
        ancestors,
        text_of,
        custom_rules,
        window_title,
        buttons,
        on_button,
    )


def _add_button(
    node: object,
    name: str,
    ancestors: list[object],
    text_of: NodeText,
    custom_rules: list[str],
    window_title: str,
    buttons: list[ButtonHit],
    on_button: Callable[[ButtonHit, object], None] | None,
) -> None:
    levels: list[str] = []
    for ancestor in ancestors[:5]:
        try:
            children = list(ancestor.GetChildren())  # type: ignore[attr-defined]
        except Exception:
            children = []
        chunks = [text_of(child).strip() for child in children[:40]]
        levels.append("\n".join(chunk[:400] for chunk in chunks if chunk))
    context = choose_context(levels, custom_rules)
    runtime_id = _runtime_id(node, name, context)
    if any(button.runtime_id == runtime_id for button in buttons):
        return
    buttons.append(
        ButtonHit(
            name=name,
            runtime_id=runtime_id,
            context_text=context,
            enabled=_flag(node, "IsEnabled", True),
            offscreen=_flag(node, "IsOffscreen", False),
            window_title=window_title,
        )
    )
    if on_button is not None:
        on_button(buttons[-1], node)


def _is_skip_label(name: str) -> bool:
    label = normalize_label(name)
    return label == "skip" or label.startswith("skip ")


def _take_run_sibling(
    skip_node: object,
    ancestors: list[object],
    text_of: NodeText,
    extra_labels: list[str],
    custom_rules: list[str],
    window_title: str,
    buttons: list[ButtonHit],
    notes: list[str],
    on_button: Callable[[ButtonHit, object], None] | None,
) -> None:
    """The blue Run button often has no useful name. It sits in the same row as Skip."""
    pool = _row_children(ancestors)
    if not pool:
        return
    candidates: list[tuple[int, object, str]] = []
    seen: list[str] = []
    for index, child in enumerate(pool):
        if child is skip_node:
            continue
        if _control_type(child) in _IGNORE_TYPES | {"DocumentControl", "EditControl", "TreeControl"}:
            continue
        label = _visible_label(child, text_of)
        if len(label) > 80:
            continue
        if label:
            seen.append(label)
        else:
            seen.append("без назви")
        if label and _is_blocked_label(label, extra_labels):
            continue
        if label and _is_not_run(label):
            continue
        candidates.append((index, child, label))
    if not candidates:
        if seen and not any(note.startswith("поруч із Skip") for note in notes):
            notes.append("поруч із Skip: " + ", ".join(seen[:6]))
        return
    named = [item for item in candidates if _is_run_label(item[2], extra_labels)]
    clickable = [item for item in candidates if _control_type(item[1]) in _CLICKABLE_TYPES]
    chosen = _rightmost(named or clickable or candidates)
    _index, node, label = chosen
    hit_name = label if is_approval_button(label, extra_labels)[0] else "Run"
    _add_button(node, hit_name, ancestors, text_of, custom_rules, window_title, buttons, on_button)
    if hit_name == "Run" and not any(note.startswith("кнопку Run взято") for note in notes):
        shown = label or "без назви"
        notes.append(f"кнопку Run взято поруч із Skip ({shown})")


def _row_children(ancestors: list[object]) -> list[object]:
    if not ancestors:
        return []
    try:
        children = list(ancestors[0].GetChildren())  # type: ignore[attr-defined]
    except Exception:
        children = []
    if len(children) <= 2 and len(ancestors) > 1:
        try:
            wider = list(ancestors[1].GetChildren())  # type: ignore[attr-defined]
        except Exception:
            wider = []
        if len(wider) > len(children):
            return wider
    return children


def _is_blocked_label(label: str, extra_labels: list[str]) -> bool:
    _approved, reason = is_approval_button(label, extra_labels)
    return reason.startswith("кнопку")


def _is_run_label(label: str, extra_labels: list[str]) -> bool:
    if is_approval_button(label, extra_labels)[0]:
        return True
    return bool(re.search(r"(^|[^a-z])run([^a-z]|$)", normalize_label(label)))


def _is_not_run(label: str) -> bool:
    text = normalize_label(label)
    return any(word in text for word in _NOT_RUN_WORDS)


def _rightmost(candidates: list[tuple[int, object, str]]) -> tuple[int, object, str]:
    def key(item: tuple[int, object, str]) -> tuple[int, int]:
        index, child, _label = item
        rect = getattr(child, "BoundingRectangle", None)
        left = getattr(rect, "left", None) if rect is not None else None
        if isinstance(rect, (tuple, list)) and rect:
            left = rect[0]
        if isinstance(left, (int, float)):
            return int(left), index
        return index, index

    return max(candidates, key=key)


def _visible_label(node: object, text_of: NodeText) -> str:
    lines = [line.strip() for line in text_of(node).splitlines() if line.strip()]
    child_bits: list[str] = []
    try:
        children = list(node.GetChildren())  # type: ignore[attr-defined]
    except Exception:
        children = []
    for child in children[:6]:
        bit = text_of(child).split("\n", 1)[0].strip()
        if bit and bit not in lines and bit not in child_bits:
            child_bits.append(bit)
    options = lines + child_bits
    for option in options:
        if is_approval_button(option)[0] or _is_skip_label(option):
            return option
    if lines:
        return lines[0]
    return " ".join(child_bits)[:160]


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
    parts: list[str] = []
    for attr in ("Name", "HelpText", "AutomationId"):
        value = str(getattr(node, attr, "") or "").strip()
        if value and value not in parts:
            parts.append(value)
    aria = str(getattr(node, "AriaProperties", "") or "")
    match = re.search(r"(?:^|;)\s*label=([^;]+)", aria, re.IGNORECASE)
    if match:
        label = match.group(1).strip().strip("\"'")
        if label and label not in parts:
            parts.append(label)
    value = str(getattr(node, "Value", "") or "").strip()
    if value and value not in parts:
        parts.append(value)
    return "\n".join(parts)


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
