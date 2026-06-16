import pytest
from PyQt5.QtCore import QTime
from PyQt5.QtWidgets import QApplication, QMessageBox
from test_scheduler import add_token_with_group

import gui
from config import ConfigManager, Group, MemoryStore
from gui import APP_TITLE, ErrorDialog, GroupDialog, MainWindow, TokenDialog
from job_store import JobStore
from scheduler import PostData, PostScheduler


@pytest.fixture
def sched(tmp_path, monkeypatch):
    cfg = ConfigManager(str(tmp_path / "config.json"), MemoryStore())
    add_token_with_group(cfg, "t1", "g1", "42")
    cfg.set_selection("t1", "g1")

    s = PostScheduler(config=cfg, store=JobStore(str(tmp_path / "jobs.json")))
    # keep the real worker thread out of the tests
    monkeypatch.setattr(s, "ensure_worker", lambda: None)
    return s


@pytest.fixture
def window(qtbot, sched):
    win = MainWindow(sched)
    qtbot.addWidget(win)
    return win


@pytest.fixture
def boxes(monkeypatch):
    """Replace QMessageBox with a recorder; question() answers Yes."""
    recorded = []

    class FakeBoxes:
        Yes = QMessageBox.Yes

        @staticmethod
        def _add(kind, text):
            recorded.append((kind, text))
            return QMessageBox.Ok

        @staticmethod
        def warning(parent, title, text):
            return FakeBoxes._add("warning", text)

        @staticmethod
        def information(parent, title, text):
            return FakeBoxes._add("information", text)

        @staticmethod
        def critical(parent, title, text):
            return FakeBoxes._add("critical", text)

        @staticmethod
        def question(parent, title, text):
            recorded.append(("question", text))
            return QMessageBox.Yes

    monkeypatch.setattr(gui, "QMessageBox", FakeBoxes)
    return recorded


# -- main window ------------------------------------------------------------

def test_window_builds_with_three_tabs(qtbot, window):
    assert window.windowTitle() == APP_TITLE
    assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == \
        ["Post", "Schedule", "Status"]


def test_window_loads_selection_from_config(qtbot, window):
    assert window.token_combo.currentText() == "t1"
    assert window.group_combo.currentText() == "g1"


def test_status_log_escapes_html(qtbot, window):
    window._log("<b>bold</b>")
    assert "<b>bold</b>" in window.log_view.toPlainText()


def test_close_event_stops_the_scheduler(qtbot, window):
    window.close()
    assert window.scheduler._stop.is_set()


# -- dialogs -----------------------------------------------------------------

def test_token_dialog_saves_token(qtbot, window, boxes):
    dialog = TokenDialog(window, window.scheduler.config)
    qtbot.addWidget(dialog)
    dialog.name_edit.setText("t2")
    dialog.value_edit.setText("v2")
    dialog._save()
    assert "t2" in window.scheduler.config.token_names()
    assert boxes == []


def test_token_dialog_rejects_empty_input(qtbot, window, boxes):
    dialog = TokenDialog(window, window.scheduler.config)
    qtbot.addWidget(dialog)
    dialog.name_edit.setText("t2")
    dialog._save()
    assert "t2" not in window.scheduler.config.token_names()
    assert boxes[0][0] == "warning"


def test_group_dialog_validates_group_id(qtbot, window, boxes):
    token = window.scheduler.config.get_token("t1")
    dialog = GroupDialog(window, token)
    qtbot.addWidget(dialog)

    dialog.name_edit.setText("g2")
    dialog.id_edit.setText("abc")
    dialog._save()
    assert token.get_group("g2") is None
    assert boxes[0][0] == "warning"

    dialog.id_edit.setText("-123456")
    dialog._save()
    assert token.get_group("g2").group_id == "-123456"


def test_error_dialog_formats_details_and_copies(qtbot, window):
    details = {"post_time": "2099-01-01 09:00", "group": "g1",
               "attempt": 1, "error": "ClientError: captcha"}
    dialog = ErrorDialog(window, "Posting error for 2099-01-01 09:00", details)
    qtbot.addWidget(dialog)

    text = dialog._format(details)
    assert "2099-01-01 09:00" in text
    assert "captcha" in text

    dialog._copy()
    clipboard = QApplication.clipboard()
    assert clipboard is not None
    assert "2099-01-01 09:00" in clipboard.text()

