"""Runtime files live in a per-user data dir."""

import logging
import os
import shutil
import sys

log = logging.getLogger(__name__)

APP_DIR_NAME = "VKPostScheduler"

# files the pre-1.2 app kept in the working directory
STATE_FILES = ("vk_config.json", "jobs_state.json", "error.log", "crash.log")


def data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP_DIR_NAME)


def data_path(name: str) -> str:
    return os.path.join(data_dir(), name)


def migrate_legacy_files() -> None:
    """Move state files left by older versions into the data dir."""
    target = data_dir()
    os.makedirs(target, exist_ok=True)
    sources = [os.getcwd()]
    if getattr(sys, "frozen", False):
        sources.append(os.path.dirname(sys.executable))

    for src_root in sources:
        if os.path.abspath(src_root) == os.path.abspath(target):
            continue
        for name in STATE_FILES:
            _move(os.path.join(src_root, name), os.path.join(target, name))
        _move(os.path.join(src_root, "logs"), os.path.join(target, "logs"))


def _move(src: str, dst: str) -> None:
    if not os.path.exists(src) or os.path.exists(dst):
        return
    try:
        shutil.move(src, dst)
        log.info("moved %s into the data dir", src)
    except OSError as e:
        log.error("could not move %s into the data dir: %s", src, e)
