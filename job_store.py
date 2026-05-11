"""Persistent job queue and photo rotation state (jobs_state.json)."""

import json
import logging
import os
import threading
from typing import List, Optional

log = logging.getLogger(__name__)


class JobStore:
    """Queued jobs, plan content and rotations in one locked json file."""

    def __init__(self, path: str = "jobs_state.json"):
        self.path = path
        self.lock = threading.RLock()
        # (mtime_ns, size) -> parsed doc; skip re-parsing when unchanged
        self._cache = None

    # -- jobs ----------------------------------------------------------------

    def load_jobs(self) -> List[dict]:
        """Jobs with their post_data reattached from the plan's shared copy."""
        with self.lock:
            doc = self._load_doc()
            shared = doc.get("post_data")
            jobs = []
            for row in self._valid_rows(doc.get("jobs", [])):
                job = dict(row)
                if "post_data" not in job and isinstance(shared, dict):
                    # own copy, not the cached one
                    job["post_data"] = dict(shared)
                jobs.append(job)
            return jobs

    def save_jobs(self, jobs: List[dict]) -> None:
        with self.lock:
            doc = self._load_doc()
            doc["jobs"] = list(jobs)
            self._save_doc(doc)

    def add_jobs(self, new_jobs: List[dict],
                 post_data: Optional[dict] = None) -> None:
        """Append jobs to the plan; post_data stored once."""
        if not new_jobs and post_data is None:
            return
        with self.lock:
            doc = self._load_doc()
            if post_data is not None:
                doc["post_data"] = post_data
                # on disk the content is stored once, at the top level
                new_jobs = [{k: v for k, v in job.items() if k != "post_data"}
                            for job in new_jobs]
            doc["jobs"] = self._valid_rows(doc.get("jobs", [])) + list(new_jobs)
            self._save_doc(doc)

    def remove_by_post_time(self, post_time: str) -> bool:
        with self.lock:
            doc = self._load_doc()
            rows = self._valid_rows(doc.get("jobs", []))
            rest = [j for j in rows if j.get("post_time") != post_time]
            if len(rest) == len(rows):
                return False
            doc["jobs"] = rest
            self._save_doc(doc)
            return True

    def clear_jobs(self) -> None:
        with self.lock:
            doc = self._load_doc()
            doc["jobs"] = []
            self._save_doc(doc)

    def pending_count(self) -> int:
        with self.lock:
            return len(self._valid_rows(self._load_doc().get("jobs", [])))

    # -- photo rotation --------------------------------------------------------

    def get_rotation(self, key: str) -> int:
        with self.lock:
            return (self._load_doc().get("rotations", {})
                    .get(key, {}).get("last_index", -1))

    def set_rotation(self, key: str, last_index: int) -> None:
        with self.lock:
            doc = self._load_doc()
            doc.setdefault("rotations", {}).setdefault(key, {})["last_index"] = last_index
            self._save_doc(doc)

    def reset_rotation(self, key: str) -> None:
        with self.lock:
            doc = self._load_doc()
            if key in doc.get("rotations", {}):
                del doc["rotations"][key]
                self._save_doc(doc)

    # -- raw io (call under the lock) --------------------------------------------

    def _valid_rows(self, raw) -> List[dict]:
        # skip junk rows instead of letting one stall the queue
        rows = [j for j in raw
                if isinstance(j, dict) and isinstance(j.get("post_time"), str)
                and j.get("post_time")]
        if len(rows) != len(raw):
            log.warning("dropped %d malformed job(s) from %s",
                        len(raw) - len(rows), self.path)
        return rows

    def _stat_key(self):
        try:
            st = os.stat(self.path)
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def _load_doc(self) -> dict:
        key = self._stat_key()
        if key is not None and self._cache and self._cache[0] == key:
            return self._cache[1]
        self._cache = None
        if key is None:
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except (json.JSONDecodeError, OSError, ValueError) as e:
            backup = self.path + ".corrupt.bak"
            log.error("%s is unreadable (%s), backed up to %s, starting empty",
                      self.path, e, backup)
            try:
                os.replace(self.path, backup)
            except OSError:
                pass
            return {}
        if not isinstance(doc, dict):
            doc = {}
        self._cache = (key, doc)
        return doc

    def _save_doc(self, doc: dict) -> None:
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, self.path)
        except OSError as e:
            log.error("failed to write %s: %s", self.path, e)
            self._cache = None  # next read must see what is actually on disk
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            return
        key = self._stat_key()
        self._cache = (key, doc) if key is not None else None
