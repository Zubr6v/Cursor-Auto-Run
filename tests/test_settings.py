from cursor_auto_run.autostart import launch_command
from cursor_auto_run.history_store import append_history, load_history
from cursor_auto_run.hotkey import parse_hotkey
from cursor_auto_run.models import Activity
from cursor_auto_run.settings_store import Settings, load_settings, save_settings
from cursor_auto_run.win_scanner import is_cursor_executable


def test_settings_roundtrip_and_limits(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(
        Settings(
            auto_run=True,
            mode="normal",
            delay_ms=90_000,
            custom_commands=["  pytest -q  ", ""],
            extra_labels=["Run command"],
            click_count=4,
            hotkey="Ctrl+Alt+A",
        ),
        path,
    )
    loaded = load_settings(path)
    assert loaded.auto_run is True
    assert loaded.mode == "normal"
    assert loaded.delay_ms == 5000
    assert loaded.custom_commands == ["pytest -q"]
    assert loaded.extra_labels == ["Run command"]
    assert loaded.click_count == 4
    assert load_settings(tmp_path / "missing.json").mode == "safe"


def test_history_keeps_the_newest_rows(tmp_path):
    path = tmp_path / "history.jsonl"
    for index in range(5):
        append_history(
            Activity(f"t{index}", "skipped", "Run", "pytest", "причина"),
            path,
            limit=3,
        )
    rows = load_history(path, limit=10)
    assert [row.at for row in rows] == ["t2", "t3", "t4"]


def test_hotkey_requires_a_modifier():
    parsed = parse_hotkey("Ctrl+Alt+A")
    assert parsed is not None
    modifiers, virtual_key = parsed
    assert modifiers & 0x0002
    assert modifiers & 0x0001
    assert virtual_key == ord("A")
    assert parse_hotkey("A") is None
    assert parse_hotkey("Ctrl") is None
    assert parse_hotkey("Ctrl+F12")[1] == 0x7B


def test_launch_command_is_quoted_and_minimized():
    command = launch_command()
    assert command.startswith('"')
    assert "--minimized" in command


def test_cursor_process_name_is_exact():
    assert is_cursor_executable(r"C:\Users\me\AppData\Local\Programs\cursor\Cursor.exe")
    assert is_cursor_executable(r"C:\cursor\cursor.exe")
    assert not is_cursor_executable(r"C:\Windows\System32\consent.exe")
    assert not is_cursor_executable(r"C:\Apps\CursorHelper.exe")
