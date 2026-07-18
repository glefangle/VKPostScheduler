"""PyQt interface for the scheduler."""

from vkpostscheduler import APP_TITLE
from vkpostscheduler.gui.dialogs import ErrorDialog, GroupDialog, TokenDialog
from vkpostscheduler.gui.main_window import MainWindow

__all__ = ["APP_TITLE", "ErrorDialog", "GroupDialog", "MainWindow",
           "TokenDialog"]
