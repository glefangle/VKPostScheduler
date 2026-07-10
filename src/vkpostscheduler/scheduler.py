"""Job queue and worker thread; posting lives in a PostClient backend."""

import datetime
import logging
import os
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from vkpostscheduler import paths
from vkpostscheduler.config import ConfigManager
from vkpostscheduler.job_store import Job, JobStore
from vkpostscheduler.posting_client import ClientError, PostClient, PublishTimeInPastError
from vkpostscheduler.schedule_time import job_key, parse_publish_time

log = logging.getLogger(__name__)

MAX_RETRIES = 3
# the pause gives the error dialog time to be read
ERROR_WAIT = 60

PHOTO_EXTS = (".jpg", ".jpeg", ".png")
ROTATION_KEY = "photos"

# outcome of _wait_while_paused (the backoff wait only ever yields ok/stopped)
WaitOutcome = Literal["ok", "resumed", "stopped"]


@dataclass
class PostData:
    text: str = ""
    photo_paths: list[str] = field(default_factory=list)
    different_posts: bool = False
    gif_name: str = ""
    gif_transform: bool = True
    sleep_time: int = 1


class PostScheduler:
    """Owns the queue and worker thread; callbacks fire from the worker."""

    def __init__(self, config: ConfigManager | None = None,
                 store: JobStore | None = None,
                 client: PostClient | None = None):
        self.config = config or ConfigManager(paths.data_path("vk_config.json"))
        self.store = store or JobStore(paths.data_path("jobs_state.json"))
        self.client = client

        self._cond = threading.Condition()
        self._jobs: deque[Job] = deque()
        self._paused = False
        self._stopping = False
        self._worker_thread: threading.Thread | None = None
        # bumped on plan replacement; old-plan jobs still queued are dropped
        self._generation = 0
        self._cancelled_post_times: set[str] = set()

        self._total = 0
        self._ok = 0
        self._failed = 0
        self._last_status_at = 0.0

        # gui hooks; always called from the worker thread
        self.on_status: Callable[[str], None] | None = None
        self.on_progress: Callable[[], None] | None = None
        self.on_error: Callable[[str, dict[str, Any]], None] | None = None

    # -- scheduling -----------------------------------------------------------

    def validate(self, post: PostData, start: datetime.date, end: datetime.date,
                 times: Sequence[datetime.time]) -> str | None:
        """Return a human-readable problem, or None when input is fine."""
        token_name, group_name = self.config.get_selection()
        if not token_name:
            return "Select a token first."
        token = self.config.get_token(token_name)
        if not token:
            return f"Token '{token_name}' no longer exists, pick another one."
        if not group_name or not token.get_group(group_name):
            return f"Target '{group_name}' not found in token '{token_name}', pick a target."
        if start > end:
            return "Start date is after end date."
        if not times:
            return "Add at least one posting time."
        if not (post.text and post.text.strip()) and not post.photo_paths:
            return "Post needs text or at least one image."
        return None

    def schedule(self, post: PostData, start: datetime.date, end: datetime.date,
                 times: Sequence[datetime.time]) -> tuple[bool, str | None]:
        """Queue one job per date/time pair. Replaces any pending plan."""
        error = self.validate(post, start, end, times)
        if error:
            return False, error

        self._throw_out_plan()
        if post.different_posts:
            # restart the photo rotation for each new plan
            self.store.reset_rotation(ROTATION_KEY)

        token_name, group_name = self.config.get_selection()
        if not token_name or not group_name:
            # validate() has ruled this out; narrow so _build_jobs gets str
            return False, "Select a token and a target first."
        jobs, exhausted = self._build_jobs(post, start, end, list(times),
                                           token_name, group_name)
        if not jobs:
            return False, "Nothing to schedule."

        shared = self._shared_post_data(post)
        for job in jobs:
            job["post_data"] = shared
        self._enqueue(jobs)
        self.store.add_jobs(jobs, post_data=shared)
        self._total = len(jobs)
        self.ensure_worker()
        self._status(f"Scheduled {len(jobs)} posts, working in the background.",
                     important=True)
        self._progress()
        if exhausted:
            self._status(f"Stopped early: only {len(post.photo_paths)} images for "
                         f"the 'different posts' mode.", important=True)
        return True, None

    def _build_jobs(self, post: PostData, start: datetime.date, end: datetime.date,
                    times: Sequence[datetime.time], token_name: str,
                    group_name: str) -> tuple[list[Job], bool]:
        jobs: list[Job] = []
        exhausted = False
        photo_idx: int | None = None
        if post.different_posts and post.photo_paths:
            photo_idx = self.store.get_rotation(ROTATION_KEY) + 1

        day = start
        while day <= end and not exhausted:
            for t in times:
                job: Job = {
                    "post_time": job_key(day, t),
                    "attempt": 0,
                    "token_name": token_name,
                    "group_name": group_name,
                    "sleep_time": post.sleep_time,
                    "generation": self._generation,
                }
                if photo_idx is not None:
                    if photo_idx >= len(post.photo_paths):
                        exhausted = True
                        break
                    job["photo_index"] = photo_idx
                    photo_idx += 1
                jobs.append(job)
            day += datetime.timedelta(days=1)

        if photo_idx is not None:
            self.store.set_rotation(ROTATION_KEY, photo_idx - 1)
        return jobs, exhausted

    @staticmethod
    def _shared_post_data(post: PostData) -> dict[str, Any]:
        """The plan's content as one shaared copy, stored once."""
        return {
            "text": post.text,
            "photo_paths": list(post.photo_paths),
            "different_posts": post.different_posts,
            "gif_name": post.gif_name,
            "gif_transform": post.gif_transform,
        }

    def _throw_out_plan(self) -> None:
        with self._cond:
            self._generation += 1
            self._cancelled_post_times.clear()
            self._jobs.clear()
        self.store.clear_jobs()
        self._total = 0
        self._ok = 0
        self._failed = 0

    # -- queue control ----------------------------------------------------------

    def reload_pending(self) -> int:
        """Load persisted jobs back into the queue after a restart."""
        jobs = self.store.load_jobs()
        for job in jobs:
            job.setdefault("attempt", 0)
            job.setdefault("generation", self._generation)
        self._enqueue(jobs)
        if jobs:
            self._total = len(jobs)
        return len(jobs)

    def cancel_job(self, post_time: str) -> bool:
        """Drop one job; queued copies are marked cancelled."""
        if not post_time:
            return False
        self._cancelled_post_times.add(post_time)
        removed = self.store.remove_by_post_time(post_time)
        if removed:
            self._progress()
        return removed

    def clear_all(self) -> None:
        self._throw_out_plan()
        self._status("All pending jobs cleared.", important=True)
        self._progress()

    def pause(self) -> None:
        self._set_paused(True)
        self._status("Queue paused.", important=True)
        self._progress()

    def resume(self) -> None:
        self._set_paused(False)
        self.ensure_worker()
        self._status("Queue resumed.", important=True)
        self._progress()

    def is_paused(self) -> bool:
        with self._cond:
            return self._paused

    def stop(self, preserve_jobs: bool = True) -> None:
        """Stop the worker; pending jobs stay on disk unless preserve_jobs=False."""
        with self._cond:
            self._stopping = True
            self._paused = False
            if not preserve_jobs:
                self._throw_out_plan()
            self._cond.notify_all()

        thread = self._worker_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)
            if thread.is_alive():
                log.warning("worker thread did not stop within 5s")
        self._progress()

    def shutdown(self) -> None:
        self.stop(preserve_jobs=True)

    def ensure_worker(self) -> None:
        """Start the worker thread unless one is still running."""
        thread = self._worker_thread
        if thread is not None and thread.is_alive():
            if not self._stopping:
                return
            thread.join(timeout=10)
            if thread.is_alive():
                return
        with self._cond:
            self._stopping = False
            self._worker_thread = threading.Thread(
                target=self._worker, name="poster", daemon=True)
            self._worker_thread.start()

    def current_jobs(self) -> list[dict[str, Any]]:
        """Pending jobs with display info for the status tab."""
        result: list[dict[str, Any]] = []
        for job in self.store.load_jobs():
            info: dict[str, Any] = {
                "post_time": job.get("post_time", "?"),
                "attempt": job.get("attempt", 0),
                "status": "pending",
            }
            plan_paths = self._plan_photo_paths(job.get("post_data", {}))
            if "photo_index" in job and 0 <= job["photo_index"] < len(plan_paths):
                info["photo"] = os.path.basename(plan_paths[job["photo_index"]])
                info["photo_no"] = job["photo_index"] + 1
                info["photo_total"] = len(plan_paths)
            elif plan_paths:
                info["photo"] = os.path.basename(plan_paths[0])
                info["photo_no"] = 1
                info["photo_total"] = 1
            result.append(info)
        return result

    def stats(self) -> dict[str, int]:
        pending = self.store.pending_count()
        done = self._ok + self._failed
        return {
            "total": max(self._total, done + pending),
            "completed": done,
            "ok": self._ok,
            "failed": self._failed,
            "pending": pending,
        }

    # -- worker -----------------------------------------------------------------

    def _worker(self):
        log.info("worker started")
        while not self._stop.is_set():
            if self._pause.is_set():
                self._pause.wait(0.5)
                continue
            try:
                job = self.queue.get(timeout=0.5)
            except Empty:
                continue

            if self._is_stale(job):
                continue

            try:
                self._execute(job)
            except Exception as e:
                if self._handle_failure(job, e) == "stopped":
                    break
            else:
                self._finish_success(job)

            if not self._stop.is_set() and not self._pause.is_set():
                time.sleep(max(0, job.get("sleep_time", 1)))
        log.info("worker stopped")

    def _is_stale(self, job: dict) -> bool:
        if job.get("generation", self._generation) != self._generation:
            log.debug("dropping stale job %s", job.get("post_time"))
            return True
        post_time = job.get("post_time")
        if post_time in self._cancelled_post_times:
            self._cancelled_post_times.discard(post_time)
            log.debug("dropping cancelled job %s", post_time)
            return True
        return False

    def _execute(self, job: dict):
        post_time = job["post_time"]
        post_data = job.get("post_data", {})
        self._status(f"Processing {post_time}")
        if self.client is None:
            raise RuntimeError("no posting client configured")

        token = self.config.get_token(job["token_name"])
        group = token.get_group(job["group_name"]) if token else None
        if group is None:
            raise ValueError(f"Target '{job['group_name']}' no longer exists")
        token_value = self.config.token_value(job["token_name"])
        if not token_value:
            raise ValueError(f"No stored credentials for '{job['token_name']}'")

        # bail out before uploading if the slot already passed
        publish_ts = self._publish_ts(post_time)
        api = self.client.api_for(token_value)

        media = self._media_for(job, post_data)
        attachment = ""
        if media:
            attachment = self._upload_media(api, media, group.group_id, post_data)

        message = (post_data.get("text") or "").strip()
        self.client.post(api, group.group_id, message or None,
                         attachment or None, publish_ts, post_data)

    @staticmethod
    def _publish_ts(post_time: str) -> int:
        dt = datetime.strptime(post_time, "%Y-%m-%d %H:%M")
        if dt <= datetime.now():
            raise PublishTimeInPastError(
                f"publish time {post_time} has already passed")
        return int(dt.timestamp())

    @staticmethod
    def _plan_photo_paths(post_data: dict) -> list[str]:
        """The plan's images; pre-1.2 plans kept a single photo_path."""
        paths = post_data.get("photo_paths") or []
        if not paths and post_data.get("photo_path"):
            paths = [post_data["photo_path"]]
        return paths

    @classmethod
    def _media_for(cls, job: dict, post_data: dict) -> str | None:
        paths = cls._plan_photo_paths(post_data)
        if "photo_index" in job and 0 <= job["photo_index"] < len(paths):
            return paths[job["photo_index"]]
        return paths[0] if paths else None

    def _upload_media(self, api, path: str, target_id: str, post_data: dict) -> str:
        client = self.client
        if client is None:
            raise RuntimeError("no posting client configured")
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        ext = os.path.splitext(path)[1].lower()
        if ext in PHOTO_EXTS:
            return client.upload_photo(api, path, target_id)
        if ext == ".gif":
            return client.upload_gif(
                api, path, target_id,
                title=post_data.get("gif_name") or None,
                transform=post_data.get("gif_transform", True))
        raise ValueError(f"{path}: unsupported file type {ext}")

    def _finish_success(self, job: dict):
        self.store.remove_by_post_time(job["post_time"])
        self._ok += 1
        self._status(f"Posted {job['post_time']} to {job.get('group_name', '?')}")
        self._progress()

    def _handle_failure(self, job: dict, error: Exception) -> str:
        """Park a failed job for retry, or fail it for good."""
        post_time = job["post_time"]
        attempt = job.get("attempt", 0)
        log.error("job %s failed (try %d): %s", post_time, attempt + 1, error,
                  exc_info=not isinstance(error, ClientError))

        details = {
            "post_time": post_time,
            "group": job.get("group_name"),
            "attempt": attempt,
            "error": f"{type(error).__name__}: {error}",
        }

        if self._is_permanent(error):
            self._fail_job(job, f"Giving up on {post_time}, the error is not "
                                f"retryable: {error}")
            return "ok"

        # pause and tell the user; resuming skips the wait
        self._pause.set()
        self._status(f"Error on {post_time}: {error}", important=True)
        self._notify_error(f"Posting error for {post_time}", details)

        outcome = self._wait_while_paused(ERROR_WAIT)
        if outcome == "stopped":
            return "stopped"

        if attempt < MAX_RETRIES:
            backoff = (attempt + 1) * 60
            self._status(f"Retrying {post_time} in {backoff // 60} min "
                         f"(retry {attempt + 1}/{MAX_RETRIES})", important=True)
            if self._wait_out_backoff(backoff) == "stopped":
                return "stopped"
            job["attempt"] = attempt + 1
            self.queue.put(job)
        else:
            self._fail_job(job, f"{post_time} failed after "
                                f"{MAX_RETRIES} retries: {error}")
        return "ok"

    def _fail_job(self, job: dict, message: str):
        self.store.remove_by_post_time(job["post_time"])
        self._failed += 1
        self._status(message, important=True)
        self._progress()

    @staticmethod
    def _is_permanent(error: Exception) -> bool:
        if isinstance(error, (PublishTimeInPastError, FileNotFoundError)):
            return True
        if isinstance(error, ValueError):
            # bad parameters, missing group/token, unsupported file type
            return True
        if isinstance(error, ClientError):
            # the backend already decided whether retrying makes sense
            return error.permanent
        return False

    def _wait_while_paused(self, seconds: int) -> str:
        """Hold while paused, at most seconds; the error dialog's grace period."""
        for _ in range(int(seconds)):
            if self._stop.is_set():
                return "stopped"
            if not self._pause.is_set():
                return "resumed"
            time.sleep(1)
        return "ok"

    def _wait_out_backoff(self, seconds: int) -> str:
        """Count down the retry backoff; pause freezes it, stop ends it."""
        left = int(seconds)
        while left > 0:
            if self._stop.is_set():
                return "stopped"
            if self._pause.is_set():
                self._pause.wait(0.5)
                continue
            time.sleep(1)
            left -= 1
        return "ok"

    # -- gui hooks ----------------------------------------------------------------

    def _status(self, message: str, important: bool = False):
        if not self.on_status:
            return
        if not important:
            now = time.monotonic()
            if now - self._last_status_at < 0.1:
                return
            self._last_status_at = now
        try:
            self.on_status(message)
        except Exception:
            log.exception("status callback failed")

    def _progress(self):
        if not self.on_progress:
            return
        try:
            self.on_progress()
        except Exception:
            log.exception("progress callback failed")

    def _notify_error(self, message: str, details: dict):
        if not self.on_error:
            return
        try:
            self.on_error(message, details)
        except Exception:
            log.exception("error callback failed")
