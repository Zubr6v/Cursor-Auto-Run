"""Offscreen checks for the real window, not a screenshot-only mock."""

import os

from PySide6.QtWidgets import QApplication

from cursor_auto_run.controller import AppController
from cursor_auto_run.scanner import UnavailableScanner
from cursor_auto_run.settings_store import Settings
from cursor_auto_run.ui.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _window(tmp_path, **settings):
    app = QApplication.instance() or QApplication([])
    payload = Settings(auto_run=False, restore_on_startup=False, mode="safe", **settings)
    window = MainWindow(
        controller=AppController(lambda: UnavailableScanner("тест")),
        settings=payload,
        settings_path=tmp_path / "settings.json",
        history_path=tmp_path / "history.jsonl",
        resume=False,
    )
    window.show()
    app.processEvents()
    return app, window


def test_preview_follows_the_selected_mode(tmp_path):
    app, window = _window(tmp_path)
    assert window.set_preview_command("pytest -q").startswith("Дозволено")
    assert window.set_preview_command("rm -rf dist").startswith("Не натискати")
    assert "Дозволено" not in window.set_preview_command("npm install requests")
    window._mode_buttons["normal"].click()
    app.processEvents()
    assert window.set_preview_command("npm install requests").startswith("Дозволено")
    assert window.set_preview_command("git push origin main").startswith("Не натискати")
    window._mode_buttons["manual"].click()
    app.processEvents()
    assert window.set_preview_command("pytest -q").startswith("Не натискати")
    window.shutdown()


def test_switch_pause_and_stop_update_status(tmp_path):
    app, window = _window(tmp_path)
    window.switch.setChecked(True)
    app.processEvents()
    assert window.status_label.text() in {"Працює", "Запускається", "Працює, без натискань"}
    window.pause_button.click()
    app.processEvents()
    assert window.status_label.text() == "Пауза"
    assert window.pause_button.text() == "Продовжити"
    window.stop_button.click()
    app.processEvents()
    assert window.switch.isChecked() is False
    assert window.status_label.text() == "Зупинено"
    window.shutdown()
    window.controller.stop()


def test_window_renders_the_main_controls(tmp_path):
    _app, window = _window(tmp_path)
    window.resize(1080, 740)
    app = QApplication.instance()
    if app is not None:
        app.processEvents()
    image = window.centralWidget().grab()
    assert image.width() >= 800
    assert image.height() >= 500
    corner = image.toImage().pixelColor(8, 8)
    assert corner.red() < 40 and corner.green() < 40 and corner.blue() < 40
    window.grab().save("/tmp/cursor-auto-run-ui.png")
    assert window.windowTitle() == "Cursor Auto Run"
    assert window.history.columnCount() == 4
    window.shutdown()
