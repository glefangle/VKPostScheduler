"""Entry point: logging, crash handling, the Qt loop."""

import logging
import os
import sys
import traceback
from datetime import datetime
from types import TracebackType

from vkpostscheduler import paths
from vkpostscheduler.job_store import JobStore
from vkpostscheduler.scheduler import PostScheduler


def setup_logging() -> logging.Logger:
    log_dir = paths.data_path("logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"app_{datetime.now():%Y%m%d_%H%M%S}.log")

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console)

    errors = logging.FileHandler(paths.data_path("error.log"), encoding="utf-8")
    errors.setLevel(logging.ERROR)
    errors.setFormatter(fmt)
    root.addHandler(errors)

    return logging.getLogger("main")


def handle_exception(exc_type: type[BaseException], exc_value: BaseException,
                     exc_traceback: TracebackType | None) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("uncaught exception",
                     exc_info=(exc_type, exc_value, exc_traceback))
    with open(paths.data_path("crash.log"), "a", encoding="utf-8") as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)


def main() -> int:
    paths.migrate_legacy_files()
    log = setup_logging()
    sys.excepthook = handle_exception
    log.info("starting")

    # imported late so a broken Qt install hits the log
    from PyQt5.QtWidgets import QApplication

    from vkpostscheduler import APP_TITLE, __version__
    from vkpostscheduler.config import ConfigManager
    from vkpostscheduler.gui import MainWindow
    from vkpostscheduler.vk_client import VKClient

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setApplicationVersion(__version__)

    scheduler = PostScheduler(
        config=ConfigManager(paths.data_path("vk_config.json"),
                             service_name="VKPostScheduler"),
        client=VKClient(),
        store=JobStore(paths.data_path("jobs_state.json")))
    window = MainWindow(scheduler)
    window.show()
    rc = app.exec_()

    log.info("closed")
    return rc
