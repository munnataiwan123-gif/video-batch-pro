"""Dark-mode QSS for the app."""

DARK_QSS = """
* {
    font-family: "Segoe UI", "San Francisco", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: #E6E6E6;
}

QMainWindow, QWidget {
    background-color: #1E1F22;
}

QFrame#card {
    background-color: #2B2D31;
    border: 1px solid #3A3C41;
    border-radius: 8px;
}

QLabel#h1 {
    font-size: 20px;
    font-weight: 600;
    color: #FFFFFF;
}

QLabel#h2 {
    font-size: 14px;
    font-weight: 600;
    color: #FFFFFF;
    padding: 4px 0;
}

QLabel#muted {
    color: #A8A9AD;
}

QPushButton {
    background-color: #3A3C41;
    border: 1px solid #4A4C52;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 22px;
    color: #FFFFFF;
}
QPushButton:hover {
    background-color: #4A4C52;
}
QPushButton:pressed {
    background-color: #2F3136;
}
QPushButton:disabled {
    background-color: #2B2D31;
    color: #6B6D73;
    border-color: #3A3C41;
}

QPushButton#primary {
    background-color: #5865F2;
    border: 1px solid #5865F2;
    font-weight: 600;
}
QPushButton#primary:hover {
    background-color: #4752C4;
}
QPushButton#primary:disabled {
    background-color: #3A3F7A;
    color: #B5B9E8;
}

QPushButton#success {
    background-color: #23A559;
    border: 1px solid #23A559;
    font-weight: 600;
}
QPushButton#success:hover {
    background-color: #1E8C4C;
}

QPushButton#danger {
    background-color: #B33A3A;
    border: 1px solid #B33A3A;
}
QPushButton#danger:hover {
    background-color: #8F2E2E;
}

QListWidget, QTreeWidget, QTableWidget {
    background-color: #232428;
    border: 1px solid #3A3C41;
    border-radius: 6px;
    padding: 4px;
}
QListWidget::item, QTreeWidget::item {
    padding: 6px;
    border-radius: 4px;
}
QListWidget::item:selected, QTreeWidget::item:selected {
    background-color: #3E4EAE;
    color: #FFFFFF;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {
    background-color: #232428;
    border: 1px solid #3A3C41;
    border-radius: 6px;
    padding: 5px 8px;
    color: #FFFFFF;
    selection-background-color: #3E4EAE;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #5865F2;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #2B2D31;
    border: 1px solid #3A3C41;
    selection-background-color: #3E4EAE;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #3A3C41;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #5865F2;
    width: 16px;
    margin: -5px 0;
    border-radius: 8px;
}
QSlider::sub-page:horizontal {
    background: #5865F2;
    border-radius: 3px;
}

QProgressBar {
    background-color: #232428;
    border: 1px solid #3A3C41;
    border-radius: 6px;
    text-align: center;
    color: #FFFFFF;
    height: 18px;
}
QProgressBar::chunk {
    background-color: #5865F2;
    border-radius: 5px;
}

QGroupBox {
    border: 1px solid #3A3C41;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 18px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #FFFFFF;
    font-weight: 600;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #4A4C52;
    border-radius: 4px;
    background: #232428;
}
QCheckBox::indicator:checked {
    background: #5865F2;
    border-color: #5865F2;
}

QScrollBar:vertical {
    background: #1E1F22;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3A3C41;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QTabBar::tab {
    background-color: #2B2D31;
    border: 1px solid #3A3C41;
    padding: 6px 12px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #A8A9AD;
}
QTabBar::tab:selected {
    background-color: #3E4EAE;
    color: #FFFFFF;
}
"""
