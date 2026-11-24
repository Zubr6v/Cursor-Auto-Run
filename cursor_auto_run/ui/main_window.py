"""Main window: auto-run control, policy settings, and the local action log."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from cursor_auto_run import __version__
from cursor_auto_run.autostart import set_autostart
from cursor_auto_run.controller import AppController
from cursor_auto_run.decision import evaluate
from cursor_auto_run.history_store import append_history, load_history
from cursor_auto_run.models import Activity
from cursor_auto_run.safety import RunMode
from cursor_auto_run.settings_store import Settings, save_settings
from cursor_auto_run.ui.theme import STYLESHEET
from cursor_auto_run.ui.toggle import ToggleSwitch

_KIND_LABELS = {
    "clicked": "Натиснуто",
    "blocked": "Заблоковано",
    "skipped": "Пропущено",
    "error": "Помилка",
    "scan": "Сканування",
    "scheduled": "Очікування",
}
_KIND_COLORS = {
    "clicked": "#3ecf8e",
    "blocked": "#f07178",
    "error": "#f07178",
    "skipped": "#e2b340",
    "scheduled": "#9aa0a6",
    "scan": "#9aa0a6",
}


class MainWindow(QMainWindow):
    hotkeyChanged = Signal(str)

    def __init__(
        self,
        controller: AppController,
        settings: Settings,
        settings_path,
        history_path,
        resume: bool = True,
    ) -> None:
        super().__init__()
        self.controller = controller
        self._settings_path = settings_path
        self._history_path = history_path
        self._mode = RunMode.parse(settings.mode).value
        self._paused = bool(settings.paused) if resume else False
        self._clicks = int(settings.click_count)
        self._quitting = False
        self._tray: QSystemTrayIcon | None = None
        self.setWindowTitle("Cursor Auto Run")
        self.setStyleSheet(STYLESHEET)
        self.resize(1080, 740)
        self.setMinimumSize(860, 620)
        self._build()
        self._load(settings, resume)
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._drain)
        self._timer.start()
        self._setup_tray()
        self._sync_controller(start=self.switch.isChecked())

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)
        layout.addLayout(self._header())
        layout.addWidget(self._status_card())
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._settings_card())
        splitter.addWidget(self._history_card())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([430, 620])
        layout.addWidget(splitter, 1)
        self.scan_label = QLabel(
            "Програма натискає лише Invoke у вікні Cursor.exe і лише після перевірки тексту команди."
        )
        self.scan_label.setObjectName("hint")
        self.scan_label.setWordWrap(True)
        layout.addWidget(self.scan_label)

    def _header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        mark = QLabel("▸")
        mark.setObjectName("mark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(36, 36)
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("Cursor Auto Run")
        title.setObjectName("title")
        subtitle = QLabel("Підтвердження команд Cursor за вашими правилами")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        version = QLabel(__version__)
        version.setObjectName("muted")
        row.addWidget(mark)
        row.addSpacing(10)
        row.addLayout(title_box, 1)
        row.addWidget(version, alignment=Qt.AlignmentFlag.AlignTop)
        return row

    def _status_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        top = QHBoxLayout()
        self.switch = ToggleSwitch()
        self.switch.toggled.connect(lambda _checked: self._sync_controller(start=True))
        switch_text = QVBoxLayout()
        switch_text.setSpacing(0)
        auto = QLabel("Auto Run")
        auto.setObjectName("section")
        self.switch_caption = QLabel("Вимкнено")
        self.switch_caption.setObjectName("muted")
        switch_text.addWidget(auto)
        switch_text.addWidget(self.switch_caption)
        top.addWidget(self.switch)
        top.addSpacing(10)
        top.addLayout(switch_text)
        top.addStretch(1)
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(10, 10)
        self.status_label = QLabel("Зупинено")
        self.status_label.setObjectName("status")
        count_box = QVBoxLayout()
        count_box.setSpacing(0)
        count_caption = QLabel("Автонатискань")
        count_caption.setObjectName("muted")
        self.count_label = QLabel("0")
        self.count_label.setObjectName("count")
        count_box.addWidget(count_caption, alignment=Qt.AlignmentFlag.AlignRight)
        count_box.addWidget(self.count_label, alignment=Qt.AlignmentFlag.AlignRight)
        top.addWidget(self.status_dot, alignment=Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.status_label)
        top.addSpacing(18)
        top.addLayout(count_box)
        layout.addLayout(top)

        modes = QHBoxLayout()
        modes.setSpacing(0)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self._mode_buttons = {}
        for index, (mode, label) in enumerate(
            (
                (RunMode.SAFE.value, "Безпечний"),
                (RunMode.NORMAL.value, "Звичайний"),
                (RunMode.MANUAL.value, "Ручний"),
            )
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("segment", True)
            button.setObjectName(f"mode-{mode}")
            self.mode_group.addButton(button, index)
            self._mode_buttons[mode] = button
            modes.addWidget(button)
        self.mode_group.idClicked.connect(self._on_mode)
        layout.addLayout(modes)
        self.mode_hint = QLabel()
        self.mode_hint.setObjectName("muted")
        self.mode_hint.setWordWrap(True)
        layout.addWidget(self.mode_hint)

        actions = QHBoxLayout()
        self.pause_button = QPushButton("Пауза")
        self.pause_button.setObjectName("pauseButton")
        self.pause_button.clicked.connect(self._on_pause)
        self.stop_button = QPushButton("Стоп")
        self.stop_button.setObjectName("danger")
        self.stop_button.clicked.connect(self._on_stop)
        self.scan_button = QPushButton("Сканувати вікна Cursor")
        self.scan_button.setObjectName("primary")
        self.scan_button.clicked.connect(self.controller.request_scan)
        self.help_button = QPushButton("Як це працює")
        self.help_button.setObjectName("helpButton")
        self.help_button.clicked.connect(self.show_safety_notes)
        actions.addWidget(self.pause_button)
        actions.addWidget(self.stop_button)
        actions.addWidget(self.scan_button)
        actions.addStretch(1)
        actions.addWidget(self.help_button)
        layout.addLayout(actions)
        return card

    def _settings_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        heading = QLabel("Налаштування")
        heading.setObjectName("section")
        layout.addWidget(heading)

        delay_row = QHBoxLayout()
        delay_row.addWidget(QLabel("Затримка перед натисканням"))
        self.delay = QSpinBox()
        self.delay.setRange(0, 5000)
        self.delay.setSingleStep(100)
        self.delay.setSuffix(" мс")
        self.delay.setObjectName("delaySpin")
        self.delay.editingFinished.connect(lambda: self._sync_controller(start=False))
        delay_row.addWidget(self.delay)
        layout.addLayout(delay_row)

        hotkey_row = QHBoxLayout()
        hotkey_row.addWidget(QLabel("Гаряча клавіша"))
        self.hotkey = QKeySequenceEdit()
        self.hotkey.setObjectName("hotkeyEdit")
        self.hotkey.editingFinished.connect(self._on_hotkey)
        hotkey_row.addWidget(self.hotkey)
        layout.addLayout(hotkey_row)

        self.startup = QCheckBox("Запускати разом із Windows")
        self.startup.setObjectName("startupCheck")
        self.startup.toggled.connect(self._on_startup)
        self.restore = QCheckBox("Відновлювати Auto Run після запуску програми")
        self.restore.setObjectName("restoreCheck")
        self.restore.toggled.connect(lambda _checked: self._sync_controller(start=False))
        layout.addWidget(self.startup)
        layout.addWidget(self.restore)
        if sys.platform != "win32":
            self.startup.setText("Запускати разом із Windows (лише у Windows)")
            self.startup.setEnabled(False)

        layout.addWidget(self._caption("Додаткові назви кнопок"))
        self.labels = QPlainTextEdit()
        self.labels.setObjectName("labelsEdit")
        self.labels.setPlaceholderText("По одній назві на рядок, наприклад Run command")
        self.labels.setFixedHeight(64)
        layout.addWidget(self.labels)

        layout.addWidget(self._caption("Власні дозволені команди"))
        self.custom = QPlainTextEdit()
        self.custom.setObjectName("customEdit")
        self.custom.setPlaceholderText("Префікс, safe:префікс або re:вираз\ntools\\check.bat")
        self.custom.setFixedHeight(88)
        self.custom.textChanged.connect(self._update_preview)
        layout.addWidget(self.custom)

        save = QPushButton("Зберегти правила")
        save.setObjectName("saveButton")
        save.clicked.connect(lambda: self._sync_controller(start=False))
        layout.addWidget(save)

        layout.addWidget(self._caption("Перевірка команди"))
        self.command_edit = QLineEdit()
        self.command_edit.setObjectName("commandEdit")
        self.command_edit.setPlaceholderText("Наприклад: pytest -q")
        self.command_edit.textChanged.connect(self._update_preview)
        layout.addWidget(self.command_edit)
        self.verdict = QLabel("Вставте команду, щоб побачити рішення.")
        self.verdict.setObjectName("verdictLabel")
        self.verdict.setWordWrap(True)
        layout.addWidget(self.verdict)
        layout.addStretch(1)
        return card

    def _history_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        heading = QLabel("Історія дій")
        heading.setObjectName("section")
        layout.addWidget(heading)
        self.history = QTableWidget(0, 4)
        self.history.setObjectName("historyTable")
        self.history.setHorizontalHeaderLabels(["Час", "Дія", "Команда", "Пояснення"])
        self.history.verticalHeader().setVisible(False)
        self.history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history.setAlternatingRowColors(True)
        self.history.setWordWrap(False)
        header = self.history.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.history)
        return card

    def _card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        return frame

    def _caption(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("muted")
        return label

    def _load(self, settings: Settings, resume: bool) -> None:
        cleaned = settings.cleaned()
        self.switch.blockSignals(True)
        self.startup.blockSignals(True)
        self.restore.blockSignals(True)
        self.delay.setValue(cleaned.delay_ms)
        self.hotkey.setKeySequence(QKeySequence(cleaned.hotkey))
        self.startup.setChecked(cleaned.start_with_windows and sys.platform == "win32")
        self.restore.setChecked(cleaned.restore_on_startup)
        self.labels.setPlainText("\n".join(cleaned.extra_labels))
        self.custom.setPlainText("\n".join(cleaned.custom_commands))
        self._mode = cleaned.mode
        self._mode_buttons[self._mode].setChecked(True)
        active = bool(cleaned.auto_run) and resume
        self._paused = bool(cleaned.paused) and active
        self.switch.setChecked(active)
        self.switch.blockSignals(False)
        self.startup.blockSignals(False)
        self.restore.blockSignals(False)
        self.count_label.setText(str(self._clicks))
        self._refresh_mode_hint()
        self._refresh_state()
        for activity in load_history(self._history_path):
            self._insert_row(activity)

    def gather_settings(self) -> Settings:
        sequence = self.hotkey.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        return Settings(
            auto_run=self.switch.isChecked(),
            paused=self._paused and self.switch.isChecked(),
            mode=self._mode,
            delay_ms=self.delay.value(),
            start_with_windows=self.startup.isChecked(),
            restore_on_startup=self.restore.isChecked(),
            hotkey=sequence or "Ctrl+Alt+A",
            custom_commands=self.custom.toPlainText().splitlines(),
            extra_labels=self.labels.toPlainText().splitlines(),
            click_count=self._clicks,
        ).cleaned()

    def _sync_controller(self, start: bool) -> None:
        if not self.switch.isChecked():
            self._paused = False
        settings = self.gather_settings()
        save_settings(settings, self._settings_path)
        self.controller.apply(settings)
        if settings.auto_run and start:
            self.controller.start()
        elif not settings.auto_run:
            self.controller.stop()
        self._refresh_state()
        self._update_preview()

    def _on_mode(self, _button_id: int) -> None:
        for mode, button in self._mode_buttons.items():
            if button.isChecked():
                self._mode = mode
                break
        self._refresh_mode_hint()
        self._sync_controller(start=False)

    def _on_pause(self) -> None:
        if not self.switch.isChecked():
            return
        self._paused = not self._paused
        self._sync_controller(start=True)

    def _on_stop(self) -> None:
        self._paused = False
        if self.switch.isChecked():
            self.switch.setChecked(False)
        else:
            self._sync_controller(start=False)

    def _on_startup(self, checked: bool) -> None:
        if sys.platform == "win32":
            error = set_autostart(checked)
            if error:
                self.startup.blockSignals(True)
                self.startup.setChecked(False)
                self.startup.blockSignals(False)
                self.scan_label.setText(error)
                return
        self._sync_controller(start=False)

    def _on_hotkey(self) -> None:
        settings = self.gather_settings()
        self.hotkeyChanged.emit(settings.hotkey)
        self._sync_controller(start=False)

    def _refresh_mode_hint(self) -> None:
        hints = {
            RunMode.SAFE.value: "Безпечний режим підтверджує читання файлів, тести і локальну збірку.",
            RunMode.NORMAL.value: "Звичайний режим додає залежності та звичайні команди git. Публікація і видалення лишаються ручними.",
            RunMode.MANUAL.value: "Ручний режим нічого не натискає. Сканування лише показує, що видно у вікні.",
        }
        self.mode_hint.setText(hints.get(self._mode, ""))

    def _refresh_state(self) -> None:
        running = self.controller.running()
        enabled = self.switch.isChecked()
        self.switch_caption.setText("Увімкнено" if enabled else "Вимкнено")
        if enabled and self._paused:
            text, color = "Пауза", "#e2b340"
        elif enabled and running:
            text, color = "Працює", "#3ecf8e"
        elif enabled:
            text, color = "Запускається", "#e2b340"
        else:
            text, color = "Зупинено", "#8f8f8f"
        if self._mode == RunMode.MANUAL.value and enabled and not self._paused:
            text = "Працює, без натискань"
        self.status_label.setText(text)
        self.status_dot.setStyleSheet(f"background:{color};border-radius:5px;")
        self.pause_button.setText("Продовжити" if self._paused else "Пауза")
        self.pause_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled or running)
        tray_auto = getattr(self, "tray_auto", None)
        if tray_auto is not None:
            tray_auto.blockSignals(True)
            tray_auto.setChecked(enabled)
            tray_auto.blockSignals(False)

    def _update_preview(self) -> None:
        command = self.command_edit.text().strip()
        if not command:
            self.verdict.setText("Вставте команду, щоб побачити рішення.")
            self.verdict.setStyleSheet("color:#8f8f8f;")
            return
        decision = evaluate(
            "Run",
            command,
            self._mode,
            self.custom.toPlainText().splitlines(),
            self.labels.toPlainText().splitlines(),
        )
        prefix = "Дозволено" if decision.click else "Не натискати"
        self.verdict.setText(f"{prefix}. {decision.reason}")
        self.verdict.setStyleSheet("color:#3ecf8e;" if decision.click else "color:#f07178;")

    def set_preview_command(self, command: str) -> str:
        self.command_edit.setText(command)
        self._update_preview()
        return self.verdict.text()

    def _drain(self) -> None:
        click_count = None
        for item in self.controller.drain():
            kind = item[0]
            if kind == "batch":
                _kind, activities, report, click_count = item
                for activity in activities:
                    self._remember(activity)
                self._show_report(report)
            elif kind == "scan":
                self._show_report(item[1])
            elif kind == "error":
                self.scan_label.setText(str(item[1]))
                self._remember(Activity(at="", kind="error", button="", command="", reason=str(item[1])))
        if click_count is not None and click_count != self._clicks:
            self._clicks = click_count
            self.count_label.setText(str(self._clicks))
            save_settings(self.gather_settings(), self._settings_path)
        self._refresh_state()

    def _show_report(self, report) -> None:
        if report is None:
            return
        if report.error:
            self.scan_label.setText(report.error)
            return
        blocked = ""
        if report.blocked_names:
            blocked = ", відхилено: " + ", ".join(report.blocked_names[:4])
        notes = " ".join(report.notes)
        self.scan_label.setText(
            f"Вікон Cursor: {report.cursor_windows}. "
            f"Кнопок підтвердження: {len(report.buttons)}{blocked}. {notes}".strip()
        )

    def _remember(self, activity: Activity) -> None:
        if activity.at:
            append_history(activity, self._history_path)
        self._insert_row(activity)

    def _insert_row(self, activity: Activity) -> None:
        self.history.insertRow(0)
        values = [
            activity.at,
            _KIND_LABELS.get(activity.kind, activity.kind),
            activity.command,
            activity.reason,
        ]
        color = QColor(_KIND_COLORS.get(activity.kind, "#ececec"))
        for column, value in enumerate(values):
            cell = QTableWidgetItem(value)
            cell.setForeground(color)
            self.history.setItem(0, column, cell)
        while self.history.rowCount() > 300:
            self.history.removeRow(self.history.rowCount() - 1)

    def show_safety_notes(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Як працює Cursor Auto Run")
        dialog.resize(560, 460)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setHtml(_HELP_HTML)
        layout.addWidget(browser)
        close = QPushButton("Закрити")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(self.windowIcon(), self)
        tray.setToolTip("Cursor Auto Run")
        menu = QMenu()
        show_action = menu.addAction("Показати")
        show_action.triggered.connect(self._present)
        self.tray_auto = menu.addAction("Auto Run")
        self.tray_auto.setCheckable(True)
        self.tray_auto.triggered.connect(self._tray_auto)
        self.tray_pause = menu.addAction("Пауза")
        self.tray_pause.triggered.connect(self._on_pause)
        menu.addSeparator()
        quit_action = menu.addAction("Вийти")
        quit_action.triggered.connect(self.quit_application)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        tray.show()
        self._tray = tray
        self._refresh_state()

    def _tray_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._present()

    def _tray_auto(self, checked: bool) -> None:
        self.switch.setChecked(checked)

    def _present(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def toggle_auto_run(self) -> None:
        self.switch.setChecked(not self.switch.isChecked())
        self._present_status_in_tray()

    def _present_status_in_tray(self) -> None:
        if self._tray is None:
            return
        state = "увімкнено" if self.switch.isChecked() else "вимкнено"
        self._tray.showMessage("Cursor Auto Run", f"Auto Run {state}.", QSystemTrayIcon.MessageIcon.NoIcon, 1500)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._tray is not None and not self._quitting:
            event.ignore()
            self.hide()
            return
        self.shutdown()
        event.accept()

    def shutdown(self) -> None:
        self._timer.stop()
        try:
            save_settings(self.gather_settings(), self._settings_path)
        except OSError:
            pass
        self.controller.stop()
        if self._tray is not None:
            self._tray.hide()

    def quit_application(self) -> None:
        self._quitting = True
        self.shutdown()
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.quit()


_HELP_HTML = """
<h3>Що робить програма</h3>
<p>Вона шукає вікна процесу <b>Cursor.exe</b> через Microsoft UI Automation
і може викликати <b>InvokePattern.Invoke</b> на кнопці Run, Allow, Run command,
Continue, Allow once або Run in sandbox.</p>
<h3>Чого вона не робить</h3>
<ul>
<li>не надсилає клавіші і не клікає мишею;</li>
<li>не підключається до налагоджувача і не відкриває Chrome DevTools;</li>
<li>не викликає внутрішні команди Cursor;</li>
<li>не чіпає UAC, інші програми і кнопки Reject, Cancel, Deny, Skip;</li>
<li>не підтверджує запуск поза пісочницею, видалення, sudo, зміну системи,
публікацію, секрети і невідомі скрипти.</li>
</ul>
<p>Якщо текст команди не вдалося прочитати поруч із кнопкою, натискання не буде.
Власне правило не може скасувати цей список.</p>
<p>Вбудовані режими Cursor лишаються в Settings → Agents → Approvals &amp; Execution.
Ця програма їх не вимикає.</p>
"""
