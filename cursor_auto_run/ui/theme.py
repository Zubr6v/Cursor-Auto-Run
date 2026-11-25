"""Dark palette close to the Cursor desktop app."""

STYLESHEET = """
* {
    font-family: "Segoe UI", "Ubuntu", "DejaVu Sans", sans-serif;
    font-size: 13px;
    color: #ececec;
}
QMainWindow, QDialog {
    background: #101010;
}
QWidget#root {
    background: #101010;
}
QLabel#mark {
    background: #f3f3f3;
    color: #111111;
    border-radius: 10px;
    font-size: 18px;
    font-weight: 700;
}
QLabel#title {
    font-size: 22px;
    font-weight: 600;
    color: #f5f5f5;
}
QLabel#subtitle, QLabel#muted, QLabel#hint {
    color: #8f8f8f;
}
QLabel#status {
    font-weight: 600;
}
QFrame#card {
    background: #181818;
    border: 1px solid #2a2a2a;
    border-radius: 12px;
}
QLabel#section {
    font-size: 13px;
    font-weight: 600;
    color: #f0f0f0;
}
QLabel#count {
    font-size: 20px;
    font-weight: 600;
    color: #f5f5f5;
}
QPushButton {
    background: #242424;
    border: 1px solid #343434;
    border-radius: 8px;
    padding: 8px 14px;
    color: #f1f1f1;
}
QPushButton:hover {
    background: #2e2e2e;
}
QPushButton:disabled {
    color: #6d6d6d;
    background: #1a1a1a;
    border-color: #2a2a2a;
}
QPushButton#primary {
    background: #f3f3f3;
    color: #111111;
    border-color: #f3f3f3;
    font-weight: 600;
}
QPushButton#primary:hover {
    background: #ffffff;
}
QPushButton#danger {
    background: transparent;
    color: #f07178;
    border-color: #6a3036;
}
QPushButton#danger:hover {
    background: #2a1618;
}
QPushButton#danger:disabled {
    color: #6d6d6d;
    background: #1a1a1a;
    border-color: #2a2a2a;
}
QPushButton[segment="true"] {
    border-radius: 0;
    padding: 8px 16px;
    background: #161616;
    color: #c8c8c8;
}
QPushButton#mode-safe {
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
}
QPushButton#mode-manual {
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}
QPushButton[segment="true"]:checked {
    background: #f3f3f3;
    color: #111111;
    font-weight: 600;
}
QLineEdit, QPlainTextEdit, QSpinBox, QKeySequenceEdit {
    background: #121212;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: #3a3a3a;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 16px;
    background: #242424;
    border: none;
}
QTableWidget {
    background: #141414;
    alternate-background-color: #191919;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    gridline-color: #2a2a2a;
    selection-background-color: #2c2c2c;
    selection-color: #f5f5f5;
}
QHeaderView::section {
    background: #1c1c1c;
    color: #9a9a9a;
    border: none;
    border-bottom: 1px solid #2a2a2a;
    padding: 6px;
    font-weight: 600;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #4a4a4a;
    background: #141414;
}
QCheckBox::indicator:checked {
    background: #f3f3f3;
    border-color: #f3f3f3;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px;
}
QScrollBar::handle:vertical {
    background: #3a3a3a;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    height: 0;
}
QMenu {
    background: #1b1b1b;
    border: 1px solid #333333;
    padding: 4px;
}
QMenu::item {
    padding: 6px 18px;
    border-radius: 6px;
}
QMenu::item:selected {
    background: #2e2e2e;
}
QTextBrowser {
    background: #141414;
    border: none;
}
"""
