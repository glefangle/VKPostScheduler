"""Entry point: logging, crash handling, the Qt loop."""

import logging
import sys
import traceback
from datetime import datetime
import os

from scheduler import PostScheduler


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    log_file = f"logs/app_{datetime.now():%Y%m%d_%H%M%S}.log"

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console)

    errors = logging.FileHandler("error.log", encoding="utf-8")
    errors.setLevel(logging.ERROR)
    errors.setFormatter(fmt)
    root.addHandler(errors)

    return logging.getLogger("main")


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    with open("crash.log", "a", encoding="utf-8") as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)


def main():
    log = setup_logging()
    sys.excepthook = handle_exception
    log.info("starting")

    from PyQt5.QtWidgets import QApplication
    from gui import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("VK Post Scheduler")
    app.setApplicationVersion("1.0.0")

    window = MainWindow(PostScheduler())
    window.show()
    rc = app.exec_()

    log.info("closed")
    return rc


if __name__ == "__main__":
    sys.exit(main())
