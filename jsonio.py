"""json io for the state files: tmp+replace writes, *.corrupt.bak backups."""

import json
import logging
import os

log = logging.getLogger(__name__)


def read_json(path: str) -> dict:
    """Parse path, return {} when missing or broken."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError, ValueError) as e:
        backup = path + ".corrupt.bak"
        log.error("%s is unreadable (%s), moved to %s", path, e, backup)
        try:
            os.replace(path, backup)
        except OSError:
            pass
        return {}
    return doc if isinstance(doc, dict) else {}


def write_json(path: str, doc: dict, indent: int | None = None) -> bool:
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            if indent is None:
                json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
            else:
                json.dump(doc, f, ensure_ascii=False, indent=indent)
        os.replace(tmp, path)
        return True
    except OSError as e:
        log.error("failed to write %s: %s", path, e)
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        return False
