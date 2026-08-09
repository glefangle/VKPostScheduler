"""The main window: three tabs (post content, schedule, status)."""

import datetime
import html
import logging
import os
from datetime import time
from typing import Any, cast

from PyQt5.QtCore import QDate, QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from vkpostscheduler import APP_TITLE, __version__
from vkpostscheduler.config import ConfigManager, Token
from vkpostscheduler.gui import dialogs
from vkpostscheduler.gui.dialogs import ErrorDialog, GroupDialog, TokenDialog
from vkpostscheduler.gui.styles import BUTTON, BUTTON_DANGER, BUTTON_QUIET, apply_app_style
from vkpostscheduler.schedule_time import format_time, parse_time
from vkpostscheduler.scheduler import PostData, PostScheduler

log = logging.getLogger(__name__)

APP_VERSION = __version__
GIF_TRANSFORM_LABEL = "Transform GIFs to VK limits (0.66:1 - 2.5:1)"

MAX_SHOWN_PHOTOS = 3


class MainWindow(QMainWindow):
    # signals marshal worker callbacks onto the gui thread
    status_sig = pyqtSignal(str)
    progress_sig = pyqtSignal()
    error_sig = pyqtSignal(str, dict)

    # -- widgets built in the _build_* methods --------------------------------
    tabs: QTabWidget
    status_tab: QWidget
    token_combo: QComboBox
    group_combo: QComboBox
    token_add_btn: QPushButton
    token_edit_btn: QPushButton
    token_delete_btn: QPushButton
    group_add_btn: QPushButton
    group_edit_btn: QPushButton
    group_delete_btn: QPushButton
    photos_label: QLabel
    browse_btn: QPushButton
    different_check: QCheckBox
    gif_name_edit: QLineEdit
    gif_transform_check: QCheckBox
    text_edit: QTextEdit
    start_date: QDateEdit
    end_date: QDateEdit
    time_edit: QTimeEdit
    add_time_btn: QPushButton
    remove_time_btn: QPushButton
    times_list: QListWidget
    sleep_spin: QSpinBox
    schedule_btn: QPushButton
    stop_btn: QPushButton
    progress: QProgressBar
    counters: QLabel
    pause_btn: QPushButton
    clear_btn: QPushButton
    jobs_list: QListWidget
    log_view: QTextEdit

    def __init__(self, scheduler: PostScheduler):
        super().__init__()
        self.scheduler = scheduler

        self.photo_paths: list[str] = []
        self.times: list[time] = []

        scheduler.on_status = self.status_sig.emit
        scheduler.on_progress = self.progress_sig.emit
        scheduler.on_error = self.error_sig.emit
        self.status_sig.connect(self._log)
        self.progress_sig.connect(self._refresh_progress)
        self.error_sig.connect(self._show_error)

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1000, 680)
        apply_app_style()
        self._build_ui()
        self._connect()

        self._refresh_selection()
        self._refresh_progress()

        pending = scheduler.reload_pending()
        if pending:
            self._log(f"Loaded {pending} pending job(s) from the previous session.")
            scheduler.ensure_worker()

    # -- setup ---------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self.tabs.addTab(self._post_tab(), "Post")
        self.tabs.addTab(self._schedule_tab(), "Schedule")
        self.status_tab = self._status_tab()
        self.tabs.addTab(self.status_tab, "Status")

        footer = QLabel(f"{APP_TITLE} v{APP_VERSION}")
        footer.setStyleSheet("color: #6c757d; font-size: 11px;")
        root.addWidget(footer, 0, Qt.AlignmentFlag.AlignRight)

    def _post_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        accounts = QGroupBox("VK account")
        grid = QGridLayout(accounts)

        grid.addWidget(QLabel("Token:"), 0, 0)
        self.token_combo = QComboBox()
        self.token_combo.setMinimumWidth(220)
        grid.addWidget(self.token_combo, 0, 1)
        (self.token_add_btn, self.token_edit_btn,
         self.token_delete_btn) = self._crud_buttons(grid, row=0)

        grid.addWidget(QLabel("Group:"), 1, 0)
        self.group_combo = QComboBox()
        self.group_combo.setMinimumWidth(220)
        grid.addWidget(self.group_combo, 1, 1)
        (self.group_add_btn, self.group_edit_btn,
         self.group_delete_btn) = self._crud_buttons(grid, row=1)

        layout.addWidget(accounts)

        content = QGroupBox("Post content")
        form = QVBoxLayout(content)

        images_row = QHBoxLayout()
        images_row.addWidget(QLabel("Images:"))
        self.photos_label = QLabel("No files selected")
        self.photos_label.setStyleSheet("color: #6c757d; font-style: italic;")
        images_row.addWidget(self.photos_label)
        images_row.addStretch()
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setStyleSheet(BUTTON_QUIET)
        images_row.addWidget(self.browse_btn)
        form.addLayout(images_row)

        self.different_check = QCheckBox("Different posts (one image per time slot)")
        self.different_check.setChecked(True)
        form.addWidget(self.different_check)

        gif_row = QHBoxLayout()
        gif_row.addWidget(QLabel("GIF name:"))
        self.gif_name_edit = QLineEdit()
        gif_row.addWidget(self.gif_name_edit)
        form.addLayout(gif_row)

        self.gif_transform_check = QCheckBox(GIF_TRANSFORM_LABEL)
        self.gif_transform_check.setChecked(True)
        form.addWidget(self.gif_transform_check)

        form.addWidget(QLabel("Text:"))
        self.text_edit = QTextEdit()
        self.text_edit.setMaximumHeight(120)
        form.addWidget(self.text_edit)

        layout.addWidget(content)
        layout.addStretch()
        return tab

    @staticmethod
    def _crud_buttons(grid: QGridLayout, row: int) -> tuple[QPushButton, ...]:
        """The Add/Edit/Delete triple in one account grid row."""
        buttons: list[QPushButton] = []
        for col, label in enumerate(("Add", "Edit", "Delete"), start=2):
            btn = QPushButton(label)
            btn.setStyleSheet(BUTTON_QUIET)
            grid.addWidget(btn, row, col)
            buttons.append(btn)
        return tuple(buttons)

    def _schedule_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        dates = QGroupBox("Date range")
        row = QHBoxLayout(dates)
        row.addWidget(QLabel("From:"))
        self.start_date = QDateEdit(QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        row.addWidget(self.start_date)
        row.addWidget(QLabel("To:"))
        self.end_date = QDateEdit(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        row.addWidget(self.end_date)
        row.addStretch()
        layout.addWidget(dates)

        times_box = QGroupBox("Times")
        times = QVBoxLayout(times_box)
        row = QHBoxLayout()
        row.addWidget(QLabel("Time:"))
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        row.addWidget(self.time_edit)
        self.add_time_btn = QPushButton("+")
        self.add_time_btn.setStyleSheet(BUTTON_QUIET)
        self.remove_time_btn = QPushButton("-")
        self.remove_time_btn.setStyleSheet(BUTTON_QUIET)
        row.addWidget(self.add_time_btn)
        row.addWidget(self.remove_time_btn)
        row.addStretch()
        times.addLayout(row)
        self.times_list = QListWidget()
        self.times_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        times.addWidget(self.times_list)
        layout.addWidget(times_box)

        settings = QGroupBox("Settings")
        row = QHBoxLayout(settings)
        row.addWidget(QLabel("Delay between posts, sec:"))
        self.sleep_spin = QSpinBox()
        self.sleep_spin.setRange(0, 3600)
        self.sleep_spin.setValue(1)
        row.addWidget(self.sleep_spin)
        row.addStretch()
        layout.addWidget(settings)

        row = QHBoxLayout()
        self.schedule_btn = QPushButton("Schedule posts")
        self.schedule_btn.setStyleSheet(BUTTON)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setStyleSheet(BUTTON_DANGER)
        row.addWidget(self.schedule_btn)
        row.addWidget(self.stop_btn)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        return tab

    def _status_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        progress_box = QGroupBox("Progress")
        vbox = QVBoxLayout(progress_box)
        self.progress = QProgressBar()
        vbox.addWidget(self.progress)
        self.counters = QLabel("Queued: 0 | Done: 0 | Failed: 0 | Pending: 0")
        vbox.addWidget(self.counters)
        row = QHBoxLayout()
        self.pause_btn = QPushButton("Pause queue")
        self.pause_btn.setStyleSheet(BUTTON_QUIET)
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.clear_btn = QPushButton("Clear all jobs")
        self.clear_btn.setStyleSheet(BUTTON_QUIET)
        row.addWidget(self.pause_btn)
        row.addWidget(self.clear_btn)
        row.addStretch()
        vbox.addLayout(row)
        layout.addWidget(progress_box)

        jobs_box = QGroupBox("Pending jobs")
        vbox = QVBoxLayout(jobs_box)
        self.jobs_list = QListWidget()
        # uniform item sizes; per-item hints freeze the gui on big queues
        self.jobs_list.setUniformItemSizes(True)
        self.jobs_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        vbox.addWidget(self.jobs_list)
        layout.addWidget(jobs_box)

        log_box = QGroupBox("Log")
        vbox = QVBoxLayout(log_box)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        self.log_view.setMaximumHeight(220)
        vbox.addWidget(self.log_view)
        layout.addWidget(log_box)
        return tab

    def _connect(self):
        self.tabs.currentChanged.connect(lambda _: self._refresh_progress())

        self.token_combo.currentTextChanged.connect(self._on_token_changed)
        self.group_combo.currentTextChanged.connect(self._on_group_changed)
        for name in ("token_add", "token_edit", "token_delete",
                     "group_add", "group_edit", "group_delete"):
            btn = self.findChild(QPushButton, name)
            btn.clicked.connect(getattr(self, "_" + name))

        self.browse_btn.clicked.connect(self._browse_photos)
        self.add_time_btn.clicked.connect(self._add_time)
        self.remove_time_btn.clicked.connect(self._remove_time)
        self.times_list.customContextMenuRequested.connect(self._times_menu)
        self.schedule_btn.clicked.connect(self._schedule)
        self.stop_btn.clicked.connect(lambda: self.scheduler.stop(preserve_jobs=True))
        self.clear_btn.clicked.connect(self._clear_jobs)
        self.jobs_list.customContextMenuRequested.connect(self._jobs_menu)

    # -- accounts -----------------------------------------------------------------

    def _refresh_selection(self):
        config = self.scheduler.config
        names = config.token_names()
        current_token, current_group = config.get_selection()

        self.token_combo.blockSignals(True)
        self.token_combo.clear()
        self.token_combo.addItems(names)
        if current_token and current_token in names:
            self.token_combo.setCurrentText(current_token)
        elif names:
            self.token_combo.setCurrentText(names[0])
            current_token = names[0]
        self.token_combo.blockSignals(False)

        groups = config.group_names(current_token) if current_token else []
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItems(groups)
        if current_group and current_group in groups:
            self.group_combo.setCurrentText(current_group)
        elif groups:
            self.group_combo.setCurrentText(groups[0])
        self.group_combo.blockSignals(False)

        if current_token and self.group_combo.currentText():
            self.scheduler.config.set_selection(current_token,
                                                self.group_combo.currentText())
            self._load_group_data()

    def _on_token_changed(self, token_name: str):
        if not token_name:
            return
        try:
            self.scheduler.config.set_selection(token_name, None)
        except ValueError as e:
            log.error("%s", e)
            return
        groups = self.scheduler.config.group_names(token_name)
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItems(groups)
        self.group_combo.blockSignals(False)
        self.times.clear()
        self.times_list.clear()

    def _on_group_changed(self, group_name: str):
        token_name = self.token_combo.currentText()
        if not token_name or not group_name:
            return

        config = self.scheduler.config
        prev_token, prev_group = config.get_selection()
        # save the edits under the group they belong to
        if prev_token and prev_group and (prev_token, prev_group) != (token_name, group_name):
            if self.times:
                try:
                    config.set_group_schedule(prev_token, prev_group, list(self.times))
                except ValueError as e:
                    self._log(f"Could not save schedule for {prev_group}: {e}")

        config.set_selection(token_name, group_name)
        self._load_group_data()

    def _load_group_data(self):
        token_name = self.token_combo.currentText()
        group_name = self.group_combo.currentText()
        if not token_name or not group_name:
            return
        config = self.scheduler.config
        self.times = list(config.get_group_schedule(token_name, group_name))
        self.times_list.clear()
        self.times_list.addItems(self.times)
        self.text_edit.setPlainText(config.get_group_default_text(token_name, group_name))

    def _token_add(self):
        dialog = TokenDialog(self, self.scheduler.config)
        if dialog.exec_():
            self._refresh_selection()
            self._log("Token added.")

    def _token_edit(self):
        name = self.token_combo.currentText()
        if not name:
            QMessageBox.warning(self, "No token", "Select a token to edit.")
            return
        dialog = TokenDialog(self, self.scheduler.config, name)
        if dialog.exec_():
            self._refresh_selection()
            self._log("Token updated.")

    def _token_delete(self):
        name = self.token_combo.currentText()
        if not name:
            QMessageBox.warning(self, "No token", "Select a token to delete.")
            return
        if QMessageBox.question(self, "Confirm",
                                f"Delete token '{name}' with all its groups?") != QMessageBox.Yes:
            return
        self.scheduler.config.remove_token(name)
        self._refresh_selection()
        self._log("Token deleted.")

    def _group_add(self):
        token_name = self.token_combo.currentText()
        token = self.scheduler.config.get_token(token_name) if token_name else None
        if not token:
            QMessageBox.warning(self, "No token", "Select a token first.")
            return
        dialog = GroupDialog(self, token)
        if dialog.exec_():
            self._refresh_selection()
            self._log("Group added.")

    def _group_edit(self):
        token_name = self.token_combo.currentText()
        group_name = self.group_combo.currentText()
        token = self.scheduler.config.get_token(token_name) if token_name else None
        if not token or not group_name:
            QMessageBox.warning(self, "No group", "Select a group to edit.")
            return
        dialog = GroupDialog(self, token, group_name)
        if dialog.exec_():
            self._refresh_selection()
            self._log("Group updated.")

    def _group_delete(self):
        token_name = self.token_combo.currentText()
        group_name = self.group_combo.currentText()
        token = self.scheduler.config.get_token(token_name) if token_name else None
        if not token or not group_name:
            QMessageBox.warning(self, "No group", "Select a group to delete.")
            return
        if QMessageBox.question(self, "Confirm",
                                f"Delete group '{group_name}'?") != QMessageBox.Yes:
            return
        token.remove_group(group_name)
        self.scheduler.config.save()
        self._refresh_selection()
        self._log("Group deleted.")

    # -- post content ---------------------------------------------------------

    def _browse_photos(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select images", "", "Images (*.jpg *.jpeg *.png *.gif)")
        if not paths:
            return
        self.photo_paths = paths
        names = [os.path.basename(p) for p in paths]
        if len(names) == 1:
            text = names[0]
        else:
            text = ", ".join(names[:3]) + (f" and {len(names) - 3} more"
                                           if len(names) > 3 else "")
        self.photos_label.setText(text)
        self.photos_label.setStyleSheet("color: #28a745; font-weight: bold;")

    # -- schedule ----------------------------------------------------------------

    def _add_time(self):
        t = self.time_edit.time().toString("HH:mm")
        if t not in self.times:
            self.times.append(t)
            self.times_list.addItem(t)
        self._save_group_schedule()

    def _remove_time(self):
        item = self.times_list.currentItem()
        if not item:
            QMessageBox.information(self, "No selection", "Select a time to remove.")
            return
        self._drop_time(item)

    def _times_menu(self, pos):
        item = self.times_list.itemAt(pos)
        if item:
            menu = QMenu(self)
            menu.addAction(f"Remove {item.text()}",
                           lambda: self._drop_time(item))
            menu.exec_(self.times_list.mapToGlobal(pos))

    def _drop_time(self, item):
        t = item.text()
        if t in self.times:
            self.times.remove(t)
        self.times_list.takeItem(self.times_list.row(item))
        self._save_group_schedule()

    def _save_group_schedule(self):
        token_name = self.token_combo.currentText()
        group_name = self.group_combo.currentText()
        if not token_name or not group_name:
            return
        try:
            self.scheduler.config.set_group_schedule(token_name, group_name,
                                                     list(self.times))
        except ValueError as e:
            self._log(f"Schedule not saved: {e}")

    def _schedule(self):
        different = self.different_check.isChecked()
        post = PostData(
            text=self.text_edit.toPlainText().strip(),
            photo_paths=list(self.photo_paths),
            different_posts=different,
            gif_name=self.gif_name_edit.text().strip(),
            gif_transform=self.gif_transform_check.isChecked(),
            sleep_time=self.sleep_spin.value(),
        )
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")

        ok, error = self.scheduler.schedule(post, start, end, list(self.times))
        if ok:
            QMessageBox.information(self, "Scheduled",
                                    "Posts are queued, the worker will "
                                    "create them in the background.")
        else:
            QMessageBox.warning(self, "Not scheduled", error or "Unknown error")

    # -- status -----------------------------------------------------------------

    def _toggle_pause(self):
        if self.scheduler.is_paused():
            self.scheduler.resume()
        else:
            self.scheduler.pause()

    def _clear_jobs(self):
        if QMessageBox.question(
                self, "Confirm",
                "Remove all pending jobs? This cannot be undone.") != QMessageBox.Yes:
            return
        self.scheduler.clear_all()

    def _jobs_menu(self, pos):
        item = self.jobs_list.itemAt(pos)
        if not item:
            return
        post_time = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction("Remove job", lambda: self._remove_job(post_time))
        menu.exec_(self.jobs_list.mapToGlobal(pos))

    def _remove_job(self, post_time: str):
        if not post_time:
            return
        if QMessageBox.question(
                self, "Confirm", f"Remove the job for {post_time}?") != QMessageBox.Yes:
            return
        if self.scheduler.cancel_job(post_time):
            self._log(f"Removed job {post_time}.")
        else:
            QMessageBox.warning(self, "Not found", f"No pending job for {post_time}.")

    # -- worker updates -----------------------------------------------------------

    def _log(self, message: str):
        stamp = datetime.now().strftime("%H:%M:%S")
        # escape angle brackets, qt would eat them
        self.log_view.append(f"[{stamp}] {html.escape(message)}")
        bar = self.log_view.verticalScrollBar()
        if bar is not None:
            bar.setValue(bar.maximum())

    def _refresh_progress(self):
        stats = self.scheduler.stats()
        self.progress.setMaximum(max(1, stats["total"]))
        self.progress.setValue(stats["completed"])
        self.counters.setText(
            f"Queued: {stats['total']} | Done: {stats['ok']} | "
            f"Failed: {stats['failed']} | Pending: {stats['pending']}")

        self.pause_btn.setText("Resume queue" if self.scheduler.is_paused()
                               else "Pause queue")

        # skip the list rebuild while the status tab is hidden
        if self.tabs.currentWidget() is self.status_tab:
            self.jobs_list.clear()
            for job in self.scheduler.current_jobs():
                line = f"{job['post_time']}  (try {job['attempt'] + 1})"
                if "photo" in job:
                    line += f"  {job['photo']}"
                    if job.get("photo_total", 1) > 1:
                        line += f"  [{job['photo_no']}/{job['photo_total']}]"
                item = QListWidgetItem(line)
                item.setData(Qt.ItemDataRole.UserRole, job["post_time"])
                self.jobs_list.addItem(item)

    def _show_error(self, message: str, details: dict):
        self._log(message)
        self.raise_()
        self.activateWindow()
        dialog = ErrorDialog(self, message, details)
        if dialog.exec_() == QDialog.Accepted:
            self.scheduler.resume()
            self._log("Queue resumed.")
        else:
            self._log("Queue stays paused.")

    def closeEvent(self, event):
        # stop the worker but keep unfinished jobs on disk
        self.scheduler.shutdown()
        event.accept()
