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


# -- schedule tab --------------------------------------------------------------

def test_add_time_persists_to_group_schedule(qtbot, window):
    window.time_edit.setTime(QTime(9, 30))
    window._add_time()
    assert window.times == ["09:30"]
    assert window.scheduler.config.get_group_schedule("t1", "g1") == ["09:30"]


def test_duplicate_time_is_not_added(qtbot, window):
    window.time_edit.setTime(QTime(9, 30))
    window._add_time()
    window._add_time()
    assert window.times == ["09:30"]
    assert window.times_list.count() == 1


def test_remove_time_persists_removal(qtbot, window):
    window.time_edit.setTime(QTime(9, 30))
    window._add_time()
    window.time_edit.setTime(QTime(10, 0))
    window._add_time()
    window.times_list.setCurrentRow(0)
    window._remove_time()
    assert window.times == ["10:00"]
    assert window.scheduler.config.get_group_schedule("t1", "g1") == ["10:00"]


def test_group_switch_saves_schedule_under_previous_group(qtbot, window, sched):
    window.time_edit.setTime(QTime(9, 30))
    window._add_time()
    sched.config.get_token("t1").add_group(Group("g2", "43"))

    # switch through the combo signal, as in the real app
    window.group_combo.addItem("g2")
    window.group_combo.setCurrentText("g2")
    assert window.times == []  # g2 has no schedule yet

    window.group_combo.setCurrentText("g1")
    # the empty g2 state must not overwrite g1's saved schedule
    assert sched.config.get_group_schedule("t1", "g1") == ["09:30"]
    assert window.times == ["09:30"]


# -- scheduling from the gui ------------------------------------------------------

def test_schedule_queues_jobs(qtbot, window, sched, boxes):
    window.text_edit.setPlainText("hello")
    window.time_edit.setTime(QTime(9, 0))
    window._add_time()

    window._schedule()

    assert sched.store.pending_count() == 1
    job = sched.store.load_jobs()[0]
    assert job["post_data"]["text"] == "hello"
    assert boxes[0][0] == "information"


def test_schedule_without_times_shows_warning(qtbot, window, sched, boxes):
    window.text_edit.setPlainText("hello")
    window._schedule()
    assert sched.store.pending_count() == 0
    assert boxes[0][0] == "warning"
    assert "time" in boxes[0][1].lower()


# -- status tab ----------------------------------------------------------------

def test_refresh_progress_shows_counters(qtbot, window, sched):
    sched.schedule(PostData(text="hi"), "2099-01-01", "2099-01-02", ["09:00"])

    window._refresh_progress()

    assert "Queued: 2" in window.counters.text()
    assert window.progress.maximum() == 2


def test_remove_job_from_jobs_list(qtbot, window, sched, boxes):
    sched.schedule(PostData(text="hi"), "2099-01-01", "2099-01-01", ["09:00"])
    post_time = sched.store.load_jobs()[0]["post_time"]

    window._remove_job(post_time)

    assert sched.store.pending_count() == 0
    assert boxes[0][0] == "question"


def test_remove_missing_job_warns(qtbot, window, boxes):
    window._remove_job("2099-01-01 09:00")
    # confirm dialog first, then the "not found" warning
    assert [kind for kind, _ in boxes] == ["question", "warning"]
