"""Modal dialogs and the blocking message-box helpers tests monkeypatch."""

import datetime
from collections.abc import Mapping
from typing import Any

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vkpostscheduler.config import ConfigManager, Group, Token
from vkpostscheduler.gui.styles import BUTTON, BUTTON_DANGER, BUTTON_QUIET


def ask(parent: QWidget | None, title: str, text: str) -> bool:
    """Blocking yes/no question; True when confirmed."""
    return QMessageBox.question(parent, title, text) == QMessageBox.Yes


def inform(parent: QWidget | None, title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


def warn(parent: QWidget | None, title: str, text: str) -> None:
    QMessageBox.warning(parent, title, text)


class TokenDialog(QDialog):
    def __init__(self, parent: QWidget | None, config: ConfigManager,
                 token_name: str | None = None) -> None:
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
            self.value_edit.setText(config.token_value(token_name) or "")

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("VK token:", self.value_edit)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _save(self) -> None:
        name = self.name_edit.text().strip()
        value = self.value_edit.text().strip()
        if not name or not value:
            warn(self, "Check input", "Name and token are both required.")
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


class GroupDialog(QDialog):
    def __init__(self, parent: QWidget | None, token: Token,
                 group_name: str | None = None) -> None:
        super().__init__(parent)
        self.token = token
        self.group_name = group_name
        self.setWindowTitle("Edit group" if group_name else "Add group")
        self.setFixedWidth(440)

        self.name_edit = QLineEdit()
        self.id_edit = QLineEdit()
        if group_name:
            group = token.get_group(group_name)
            if group:
                self.name_edit.setText(group.name)
                self.id_edit.setText(group.group_id)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Group ID:", self.id_edit)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _save(self) -> None:
        name = self.name_edit.text().strip()
        gid = self.id_edit.text().strip()
        if not name or not gid:
            warn(self, "Check input", "Name and group ID are both required.")
            return
        # group ids are numbers, possibly negative
        try:
            int(gid.lstrip("-"))
        except ValueError:
            warn(self, "Check input", "Group ID must be a number.")
            return
        try:
            if self.group_name:
                self.token.update_group(self.group_name, Group(name, gid))
            else:
                self.token.add_group(Group(name, gid))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.accept()


