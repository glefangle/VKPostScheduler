"""Job queue and worker thread; posting lives in a PostClient backend."""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from queue import Empty, Queue
from typing import Callable, List, Optional, Tuple

from vk_api.exceptions import ApiError

from vk_client import VKClient
from vk_config import VKConfigManager

log = logging.getLogger(__name__)

MAX_RETRIES = 3
ERROR_WAIT = 60  # the pause gives the error dialog time to be read

PHOTO_EXTS = (".jpg", ".jpeg", ".png")
ROTATION_KEY = "user_photos"


class PublishTimeInPastError(Exception):
    """The publish time is in the past; nothing to retry."""


@dataclass
class PostData:
    text: str = ""
    photo_path: Optional[str] = None
    photo_paths: List[str] = field(default_factory=list)
    different_posts: bool = False
    gif_name: str = ""
    sleep_time: int = 1


class PostScheduler:
    def __init__(self, config: VKConfigManager = None, client: VKClient = None):
        self.config = config or VKConfigManager()
        self.client = client or VKClient()

        self.queue: Queue = Queue()
        # gui hooks; always called from the worker thread
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_progress: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str, dict], None]] = None

        self._worker_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        self._total = 0
        self._ok = 0
        self._failed = 0
        self._last_status_at = 0.0

        self._state_file = "jobs_state.json"

    # -- scheduling -----------------------------------------------------------

    def validate(self, post: PostData, start_date: str, end_date: str,
                 times: List[str]) -> Optional[str]:
        """Return a human-readable problem, or None when input is fine."""
        token_name, group_name = self.config.get_selection()
        if not token_name:
            return "Select a VK token first."
        token = self.config.get_token(token_name)
        if not token:
            return f"Token '{token_name}' no longer exists, pick another one."
        if not group_name or not token.get_group(group_name):
            return f"Group '{group_name}' not found in token '{token_name}', pick a group."
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return "Invalid start or end date."
        if start > end:
            return "Start date is after end date."
        if not times:
            return "Add at least one posting time."
        if not (post.text and post.text.strip()) and not post.photo_path and not post.photo_paths:
            return "Post needs text or at least one image."
        return None

    def schedule(self, post: PostData, start_date: str, end_date: str,
                 times: List[str]) -> Tuple[bool, Optional[str]]:
        """Queue one job per date/time pair. Replaces any pending plan."""
        error = self.validate(post, start_date, end_date, times)
        if error:
            return False, error

        self._throw_out_plan()
        if post.different_posts:
            # restart the photo rotation for each new plan
            self._reset_rotation(ROTATION_KEY)

        token_name, group_name = self.config.get_selection()
        jobs, exhausted = self._build_jobs(post, start_date, end_date, times,
                                           token_name, group_name)
        if not jobs:
            return False, "Nothing to schedule."

        self._add_jobs(jobs)
        for job in jobs:
            self.queue.put(job)
        self._total = len(jobs)
        self.ensure_worker()
        self._status(f"Scheduled {len(jobs)} posts, working in the background.",
                     important=True)
        self._progress()
        if exhausted:
            self._status(f"Stopped early: only {len(post.photo_paths)} images for "
                         f"the 'different posts' mode.", important=True)
        return True, None

    def _build_jobs(self, post: PostData, start_date: str, end_date: str,
                    times: List[str], token_name: str, group_name: str):
        jobs = []
        exhausted = False
        photo_idx = None
        if post.different_posts and post.photo_paths:
            photo_idx = self._get_rotation(ROTATION_KEY) + 1

        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        day = start
        while day <= end and not exhausted:
            for t in times:
                job = {
                    "post_time": f"{day:%Y-%m-%d} {t}",
                    "attempt": 0,
                    "token_name": token_name,
                    "group_name": group_name,
                    "post_data": {
                        "text": post.text,
                        "photo_path": post.photo_path,
                        "photo_paths": post.photo_paths,
                        "different_posts": post.different_posts,
                        "gif_name": post.gif_name,
                    },
                    "sleep_time": post.sleep_time,
                }
                if photo_idx is not None:
                    if photo_idx >= len(post.photo_paths):
                        exhausted = True
                        break
                    job["photo_index"] = photo_idx
                    photo_idx += 1
                jobs.append(job)
            day += timedelta(days=1)

        if photo_idx is not None:
            self._set_rotation(ROTATION_KEY, photo_idx - 1)
        return jobs, exhausted

    def _throw_out_plan(self):
        self._clear_state_jobs()
        while True:
            try:
                self.queue.get_nowait()
            except Empty:
                break
        self._total = 0
        self._ok = 0
        self._failed = 0

