"""PyQt interface for the scheduler."""

import logging
import os
from datetime import datetime

from PyQt5.QtCore import QDate, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QTabWidget, QTextEdit, QTimeEdit,
    QVBoxLayout, QWidget,
)
from PyQt5.QtGui import QFont

from scheduler import PostData, PostScheduler

log = logging.getLogger(__name__)

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


class TokenDialog(QDialog):
    def __init__(self, parent, config, token_name=None):
        super().__init__(parent)
        self.config = config
        self.token_name = token_name
        self.setWindowTitle("Edit token" if token_name else "Add token")
        self.setFixedWidth(440)

        self.name_edit = QLineEdit()
        self.value_edit = QLineEdit()
        self.value_edit.setEchoMode(QLineEdit.Password)
        if token_name:
            self.name_edit.setText(token_name)
            stored = config.token_value(token_name)
            if stored:
                self.value_edit.setText(stored)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("VK token:", self.value_edit)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _save(self):
        name = self.name_edit.text().strip()
        value = self.value_edit.text().strip()
        if not name or not value:
            QMessageBox.warning(self, "Check input", "Name and token are both required.")
            return
        try:
            if self.token_name:
                self.config.update_token(self.token_name, name, value)
            else:
                self.config.add_token(name, value)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.accept()


