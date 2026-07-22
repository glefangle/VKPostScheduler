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
