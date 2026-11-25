"""Shared data types. These objects never hold Windows UI handles."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ButtonHit:
    name: str
    runtime_id: str
    context_text: str
    enabled: bool
    offscreen: bool
    window_title: str


@dataclass
class ScanReport:
    cursor_windows: int = 0
    buttons: list[ButtonHit] = field(default_factory=list)
    blocked_names: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class InvokeResult:
    ok: bool
    detail: str


@dataclass(frozen=True)
class ClickDecision:
    click: bool
    reason: str
    command: str
    category: str


@dataclass(frozen=True)
class Activity:
    at: str
    kind: str
    button: str
    command: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "Activity":
        return cls(
            at=str(payload.get("at", "")),
            kind=str(payload.get("kind", "")),
            button=str(payload.get("button", "")),
            command=str(payload.get("command", "")),
            reason=str(payload.get("reason", "")),
        )
