"""Application entry point."""

from __future__ import annotations

import argparse
import ctypes
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from cursor_auto_run import __version__
from cursor_auto_run.controller import AppController
from cursor_auto_run.hotkey import GlobalHotkey
from cursor_auto_run.settings_store import app_directory, load_settings
from cursor_auto_run.ui.main_window import MainWindow
from cursor_auto_run.ui.theme import STYLESHEET

_SERVER_NAME = "CursorAutoRun.SingleInstance"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _configure_logging()
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CursorAutoRun.App")
    app = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
    app.setApplicationName("Cursor Auto Run")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    app.setQuitOnLastWindowClosed(False)
    icon = _load_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    server = _claim_single_instance()
    if server is None:
        return 0

    settings_path = app_directory() / "settings.json"
    history_path = app_directory() / "history.jsonl"
    settings = load_settings(settings_path)
    window = MainWindow(
        controller=AppController(),
        settings=settings,
        settings_path=settings_path,
        history_path=history_path,
        resume=settings.restore_on_startup,
    )
    if icon is not None:
        window.setWindowIcon(icon)
    relay = _HotkeyRelay()
    relay.triggered.connect(window.toggle_auto_run)
    hotkey = GlobalHotkey(relay.triggered.emit)
    hotkey_error = hotkey.start(window.gather_settings().hotkey)
    if hotkey_error:
        window.scan_label.setText(hotkey_error)

    def restart_hotkey(sequence: str) -> None:
        error = hotkey.start(sequence)
        if error:
            window.scan_label.setText(error)

    window.hotkeyChanged.connect(restart_hotkey)
    if window._tray is None:
        app.setQuitOnLastWindowClosed(True)
    server.newConnection.connect(lambda: _show_existing(server, window))
    app.aboutToQuit.connect(hotkey.stop)
    app.aboutToQuit.connect(window.shutdown)

    if args.minimized and window._tray is not None:
        window.hide()
    else:
        window.show()
    return app.exec()


class _HotkeyRelay(QObject):
    """Queues a hotkey from the Win32 thread onto the Qt thread."""

    triggered = Signal()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="cursor-auto-run", description="Cursor Auto Run")
    parser.add_argument("--minimized", action="store_true", help="start in the system tray")
    parser.add_argument("--version", action="version", version=__version__)
    return parser.parse_args(argv)


def _claim_single_instance() -> QLocalServer | None:
    probe = QLocalSocket()
    probe.connectToServer(_SERVER_NAME)
    if probe.waitForConnected(250):
        probe.write(b"show")
        probe.flush()
        probe.waitForBytesWritten(250)
        probe.disconnectFromServer()
        return None
    QLocalServer.removeServer(_SERVER_NAME)
    server = QLocalServer()
    if server.listen(_SERVER_NAME):
        return server
    probe.connectToServer(_SERVER_NAME)
    if probe.waitForConnected(250):
        probe.write(b"show")
        probe.flush()
        probe.waitForBytesWritten(250)
    return None


def _show_existing(server: QLocalServer, window: MainWindow) -> None:
    client = server.nextPendingConnection()
    if client is not None:
        client.waitForReadyRead(200)
        client.disconnectFromServer()
    window.showNormal()
    window.raise_()
    window.activateWindow()


def _load_icon() -> QIcon | None:
    path = _asset("icon.ico")
    if not path.exists():
        return None
    icon = QIcon(str(path))
    return icon if not icon.isNull() else None


def _asset(name: str) -> Path:
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    else:
        root = Path(__file__).resolve().parent.parent
    return root / "assets" / name


def _configure_logging() -> None:
    try:
        directory = app_directory()
        directory.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=directory / "app.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            encoding="utf-8",
        )
    except OSError:
        return


if __name__ == "__main__":
    raise SystemExit(main())
