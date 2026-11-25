"""A two-state switch that does not depend on a platform theme."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = False
        self.setObjectName("autoSwitch")
        self.setFixedSize(48, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool) -> None:
        value = bool(value)
        if value == self._checked:
            return
        self._checked = value
        self.update()
        self.toggled.emit(value)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.setChecked(not self._checked)
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#3ecf8e") if self._checked else QColor("#3a3a3a"))
        painter.drawRoundedRect(1, 2, 46, 24, 12, 12)
        painter.setBrush(QColor("#111111") if self._checked else QColor("#f4f4f4"))
        knob_x = 24 if self._checked else 4
        painter.drawEllipse(knob_x, 4, 20, 20)
        painter.end()
