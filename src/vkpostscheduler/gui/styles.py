"""Shared Qt style sheets for dialogs, buttons and the app."""

from PyQt5.QtWidgets import QApplication

BUTTON = """
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4a90e2, stop:1 #357abd);
    border: none; border-radius: 5px; color: white;
    padding: 8px 16px; font-weight: 500;
}
QPushButton:hover { background: #5ba0f2; }
QPushButton:pressed { background: #357abd; }
QPushButton:disabled { background: #cccccc; color: #666666; }
"""

BUTTON_DANGER = """
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #dc3545, stop:1 #c82333);
    border: none; border-radius: 5px; color: white;
    padding: 8px 16px; font-weight: 500;
}
QPushButton:hover { background: #e74c3c; }
"""

BUTTON_QUIET = """
QPushButton {
    background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px;
    color: #495057; padding: 6px 12px;
}
QPushButton:hover { background: #e9ecef; }
QPushButton:pressed { background: #dee2e6; }
"""

INPUT = """
QLineEdit, QComboBox, QTimeEdit, QDateEdit, QSpinBox {
    border: 2px solid #e9ecef; border-radius: 5px; padding: 6px 10px;
    background: white; color: #495057;
}
QLineEdit:focus, QComboBox:focus, QTimeEdit:focus, QDateEdit:focus, QSpinBox:focus {
    border-color: #4a90e2;
}
"""

MAIN_WINDOW_QSS = """
QMainWindow { background: #f8f9fa; }
QGroupBox {
    font-weight: bold; border: 2px solid #dee2e6; border-radius: 8px;
    margin-top: 10px; padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #495057;
}
QLabel { color: #495057; }
QTabWidget::pane { border: 2px solid #dee2e6; border-radius: 8px; background: white; }
QTabBar::tab {
    background: #e9ecef; border: 1px solid #dee2e6; padding: 8px 16px;
    margin-right: 2px; border-top-left-radius: 5px; border-top-right-radius: 5px;
}
QTabBar::tab:selected { background: white; border-bottom-color: white; }
QListWidget {
    border: 2px solid #e9ecef; border-radius: 5px; background: white;
    color: #495057; outline: none;
}
QListWidget::item { padding: 6px; border-bottom: 1px solid #f8f9fa; }
QListWidget::item:selected { background: #4a90e2; color: white; }
QProgressBar {
    border: 2px solid #e9ecef; border-radius: 10px; text-align: center;
    background: #f8f9fa; color: #495057; font-weight: bold;
}
QProgressBar::chunk {
    border-radius: 8px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4a90e2, stop:1 #357abd);
}
""" + INPUT


def apply_app_style() -> None:
    """Install the app-wide stylesheet on the QApplication instance."""
    app = QApplication.instance()
    if isinstance(app, QApplication):
        app.setStyleSheet(MAIN_WINDOW_QSS)
