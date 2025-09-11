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

