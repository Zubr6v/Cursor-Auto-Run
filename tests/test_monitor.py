"""Monitor tests with a fake scanner. No UI Automation calls."""

from cursor_auto_run.models import ButtonHit, InvokeResult, ScanReport
from cursor_auto_run.monitor import Monitor, MonitorConfig
from cursor_auto_run.safety import RunMode
from cursor_auto_run.tree_walk import collect_buttons


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class ScriptedScanner:
    def __init__(self, buttons: list[ButtonHit]) -> None:
        self.buttons = buttons
        self.invoked: list[str] = []

    def scan(self, extra_labels=None, custom_rules=None) -> ScanReport:
        del extra_labels, custom_rules
        return ScanReport(cursor_windows=1, buttons=list(self.buttons))

    def invoke(self, runtime_id: str) -> InvokeResult:
        self.invoked.append(runtime_id)
        return InvokeResult(True, "InvokePattern.Invoke")


def _button(name: str, context: str, runtime_id: str = "1", enabled=True, offscreen=False) -> ButtonHit:
    return ButtonHit(name, runtime_id, context, enabled, offscreen, "Cursor")


def _monitor(scanner: ScriptedScanner) -> tuple[Monitor, Clock]:
    clock = Clock()
    return Monitor(scanner, clock=clock, now_text=lambda: "2026-11-24 22:40:00"), clock


def test_click_waits_for_the_delay_and_then_invokes_once():
    scanner = ScriptedScanner([_button("Run", "pytest -q")])
    monitor, clock = _monitor(scanner)
    config = MonitorConfig(enabled=True, mode=RunMode.SAFE, delay_ms=600)
    first, _report = monitor.tick(config)
    assert [item.kind for item in first] == ["scheduled"]
    assert scanner.invoked == []
    clock.now = 0.6
    second, _report = monitor.tick(config)
    assert scanner.invoked == ["1"]
    assert monitor.click_count == 1
    assert second[-1].kind == "clicked"
    clock.now = 1.0
    third, _report = monitor.tick(config)
    assert third == []
    assert scanner.invoked == ["1"]


def test_zero_delay_invokes_on_the_same_observation():
    scanner = ScriptedScanner([_button("Allow", "git status")])
    monitor, _clock = _monitor(scanner)
    activities, _report = monitor.tick(MonitorConfig(enabled=True, mode=RunMode.SAFE, delay_ms=0))
    assert scanner.invoked == ["1"]
    assert activities[-1].kind == "clicked"


def test_dangerous_disabled_offscreen_and_paused_do_not_invoke():
    dangerous = ScriptedScanner([_button("Run", "rm -rf dist")])
    monitor, _clock = _monitor(dangerous)
    activities, _report = monitor.tick(MonitorConfig(enabled=True, mode=RunMode.NORMAL, delay_ms=0))
    assert dangerous.invoked == []
    assert activities[0].kind == "blocked"

    disabled = ScriptedScanner([_button("Run", "pytest -q", enabled=False)])
    monitor, _clock = _monitor(disabled)
    monitor.tick(MonitorConfig(enabled=True, mode=RunMode.SAFE, delay_ms=0))
    assert disabled.invoked == []

    hidden = ScriptedScanner([_button("Run", "pytest -q", offscreen=True)])
    monitor, _clock = _monitor(hidden)
    monitor.tick(MonitorConfig(enabled=True, mode=RunMode.SAFE, delay_ms=0))
    assert hidden.invoked == []

    paused = ScriptedScanner([_button("Run", "pytest -q")])
    monitor, _clock = _monitor(paused)
    activities, _report = monitor.tick(
        MonitorConfig(enabled=True, paused=True, mode=RunMode.SAFE, delay_ms=0)
    )
    assert paused.invoked == []
    assert activities[0].reason.startswith("пауза")


def test_button_that_disappears_before_the_delay_is_not_clicked():
    button = _button("Run", "pytest -q")
    scanner = ScriptedScanner([button])
    monitor, clock = _monitor(scanner)
    config = MonitorConfig(enabled=True, mode=RunMode.SAFE, delay_ms=500)
    monitor.tick(config)
    scanner.buttons = []
    clock.now = 2
    monitor.tick(config)
    assert scanner.invoked == []


def test_manual_mode_records_a_skip():
    scanner = ScriptedScanner([_button("Run", "pytest -q")])
    monitor, _clock = _monitor(scanner)
    activities, _report = monitor.tick(MonitorConfig(enabled=True, mode=RunMode.MANUAL, delay_ms=0))
    assert scanner.invoked == []
    assert activities[0].kind == "skipped"


class _Node:
    def __init__(self, name, control_type="TextControl", children=None, runtime=(1,)):
        self.Name = name
        self.ControlTypeName = control_type
        self.IsEnabled = True
        self.IsOffscreen = False
        self._children = children or []
        self._runtime = runtime

    def GetChildren(self):
        return list(self._children)

    def GetRuntimeId(self):
        return self._runtime


class _TreeScanner:
    def __init__(self, window: _Node) -> None:
        self.window = window
        self.invoked: list[str] = []

    def scan(self, extra_labels=None, custom_rules=None) -> ScanReport:
        buttons, blocked, notes = collect_buttons(
            self.window,
            window_title="Cursor",
            extra_labels=extra_labels,
            custom_rules=custom_rules,
        )
        return ScanReport(1, buttons, blocked, notes)

    def invoke(self, runtime_id: str) -> InvokeResult:
        self.invoked.append(runtime_id)
        return InvokeResult(True, "InvokePattern.Invoke")


def test_walker_uses_the_approval_card_and_ignores_reject():
    card = _Node(
        "approval",
        "GroupControl",
        [
            _Node("pytest -q"),
            _Node("Run", "ButtonControl", runtime=(7,)),
            _Node("Reject", "ButtonControl", runtime=(8,)),
        ],
    )
    window = _Node(
        "Cursor",
        "WindowControl",
        [
            _Node("rm -rf C:\\important"),
            card,
        ],
        runtime=(1,),
    )
    scanner = _TreeScanner(window)
    monitor, _clock = _monitor(scanner)
    activities, report = monitor.tick(MonitorConfig(enabled=True, mode=RunMode.SAFE, delay_ms=0))
    assert scanner.invoked
    assert "rm -rf" not in report.buttons[0].context_text
    assert any(name == "Reject" for name in report.blocked_names)
    assert activities[-1].kind == "clicked"
    assert "pytest -q" in activities[-1].command


WORD_SCRIPT = """$word = New-Object -ComObject Word.Application
$word.Visible = $false
$src = "D:\\lab\\report.doc"
$doc = $word.Documents.Open($src)
Write-Output $doc.Paragraphs.Count
$doc.Close($false)
$word.Quit()
"""


def test_run_step_next_to_skip_clicks_the_word_script():
    card = _Node(
        "approval",
        "GroupControl",
        [
            _Node(WORD_SCRIPT, "TextControl"),
            _Node("Allowlist", "SplitButtonControl", runtime=(3,)),
            _Node("Skip step", "ButtonControl", runtime=(4,)),
            _Node("Always Run", "ButtonControl", runtime=(5,)),
            _Node("Run step", "CustomControl", runtime=(6,)),
            _Node("Run", "MenuItemControl", runtime=(9,)),
        ],
    )
    window = _Node("Cursor", "WindowControl", [card], runtime=(1,))
    scanner = _TreeScanner(window)
    monitor, _clock = _monitor(scanner)
    activities, report = monitor.tick(MonitorConfig(enabled=True, mode=RunMode.SAFE, delay_ms=0))
    assert scanner.invoked == ["6"]
    assert activities[-1].kind == "clicked"
    assert "New-Object" in activities[-1].command
    assert "Skip step" in report.blocked_names
    assert "Always Run" in report.blocked_names
    assert all(button.name != "Allowlist" for button in report.buttons)


def test_menu_run_without_an_approval_card_is_ignored():
    window = _Node(
        "Cursor",
        "WindowControl",
        [_Node("Run", "MenuItemControl", runtime=(2,)), _Node("Run", "ButtonControl", runtime=(3,))],
        runtime=(1,),
    )
    _buttons, blocked, _notes = collect_buttons(window, window_title="Cursor")
    assert _buttons == []
    assert blocked == []
