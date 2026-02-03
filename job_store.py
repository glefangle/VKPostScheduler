"""Persistent job queue and photo rotation state (jobs_state.json)."""

import json
import logging
import os
import threading
from typing import List

log = logging.getLogger(__name__)


class JobStore:
    """Queued jobs, plan content and rotations in one locked json file."""

    def __init__(self, path: str = "jobs_state.json"):
        self.path = path
        self.lock = threading.RLock()

    # -- jobs ----------------------------------------------------------------

    def load_jobs(self) -> List[dict]:
        with self.lock:
            return self._read().get("jobs", [])

    def save_jobs(self, jobs: List[dict]) -> None:
        with self.lock:
            data = self._read()
            data["jobs"] = jobs
            self._write(data)

    def add_jobs(self, new_jobs: List[dict]) -> None:
        if not new_jobs:
            return
        with self.lock:
            jobs = self.load_jobs()
            jobs.extend(new_jobs)
            self.save_jobs(jobs)

    def remove_by_post_time(self, post_time: str) -> bool:
        with self.lock:
            jobs = self.load_jobs()
            rest = [j for j in jobs if j.get("post_time") != post_time]
            if len(rest) == len(jobs):
                return False
            self.save_jobs(rest)
            return True

    def clear_jobs(self) -> None:
        with self.lock:
            data = self._read()
            data["jobs"] = []
            self._write(data)

    def pending_count(self) -> int:
        return len(self.load_jobs())

    # -- photo rotation --------------------------------------------------------

    def get_rotation(self, key: str) -> int:
        return self._read().get("rotations", {}).get(key, {}).get("last_index", -1)

    def set_rotation(self, key: str, last_index: int) -> None:
        with self.lock:
            data = self._read()
            data.setdefault("rotations", {}).setdefault(key, {})["last_index"] = last_index
            self._write(data)

    def reset_rotation(self, key: str) -> None:
        with self.lock:
            data = self._read()
            if key in data.get("rotations", {}):
                del data["rotations"][key]
                self._write(data)

    # -- raw io (call under the lock) --------------------------------------------

    def _read(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError, ValueError) as e:
            log.error("cannot read %s: %s", self.path, e)
            return {}

    def _write(self, data: dict) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            log.error("failed to write %s: %s", self.path, e)
