import json
from datetime import datetime
from typing import Any

import pytest

from config import ConfigManager, Group, MemoryStore
from job_store import JobStore
from posting_client import ClientError, PublishTimeInPastError
from scheduler import ROTATION_KEY, PostData, PostScheduler


@pytest.fixture
def sched(tmp_path, monkeypatch):
    cfg = ConfigManager(str(tmp_path / "config.json"), MemoryStore())
    add_token_with_group(cfg, "t1", "g1", "42")
    cfg.set_selection("t1", "g1")

    s = PostScheduler(config=cfg, store=JobStore(str(tmp_path / "jobs.json")))
    # keep the real worker thread out of the tests
    monkeypatch.setattr(s, "ensure_worker", lambda: None)
    return s


def add_token_with_group(cfg, token_name, group_name, group_id):
    """add_token + one group, with the None-checks spelled out."""
    cfg.add_token(token_name, "secret")
    token = cfg.get_token(token_name)
    assert token is not None
    token.add_group(Group(group_name, group_id))
    return token


def make_post(**kw):
    defaults: dict[str, Any] = dict(text="hello", photo_paths=[], different_posts=False)
    defaults.update(kw)
    return PostData(**defaults)


class RecordingClient:
    """Stands in for a PostClient and remembers the calls."""

    def __init__(self):
        self.calls = []

    def api_for(self, credential):
        return {"ok": True}

    def upload_photo(self, api, path, target_id):
        self.calls.append(("photo", path, target_id))
        return path

    def upload_gif(self, api, path, target_id, title=None, transform=True):
        self.calls.append(("gif", path, target_id, title, transform))
        return path

    def post(self, api, target_id, message, attachment, publish_ts, post_data=None):
        self.calls.append(("post", target_id, message, attachment, publish_ts))
        return {}


def test_validate_no_token(tmp_path):
    cfg = ConfigManager(str(tmp_path / "c.json"), MemoryStore())
    s = PostScheduler(config=cfg, store=JobStore(str(tmp_path / "j.json")))
    problem = s.validate(make_post(), "2026-01-01", "2026-01-01", ["09:00"])
    assert problem is not None
    assert "token" in problem.lower()


def test_validate_no_group(sched):
    sched.config.set_selection("t1", None)
    problem = sched.validate(make_post(), "2026-01-01", "2026-01-01", ["09:00"])
    assert problem is not None
    assert "target" in problem.lower()


def test_validate_dates(sched):
    assert "after end date" in sched.validate(
        make_post(), "2026-05-02", "2026-05-01", ["09:00"])
    assert "Invalid" in sched.validate(
        make_post(), "02.05.2026", "2026-05-01", ["09:00"])


def test_validate_times_and_content(sched):
    assert sched.validate(make_post(), "2026-01-01", "2026-01-01", []) is not None
    problem = sched.validate(make_post(text="  "), "2026-01-01", "2026-01-01", ["09:00"])
    assert "text" in problem.lower() or "image" in problem.lower()


def test_validate_ok(sched):
    assert sched.validate(make_post(), "2026-01-01", "2026-01-02", ["09:00"]) is None


def test_schedule_replaces_previous_plan(sched):
    ok, err = sched.schedule(make_post(), "2099-01-01", "2099-01-01", ["09:00", "10:00"])
    assert (ok, err) == (True, None)
    assert sched.store.pending_count() == 2

    ok, err = sched.schedule(make_post(), "2099-02-01", "2099-02-01", ["09:00"])
    assert ok is True
    jobs = sched.store.load_jobs()
    assert [j["post_time"] for j in jobs] == ["2099-02-01 09:00"]
    assert sched.stats()["pending"] == 1


def test_schedule_rejects_bad_input(sched):
    ok, err = sched.schedule(make_post(), "2026-05-02", "2026-05-01", ["09:00"])
    assert ok is False
    assert err


def test_schedule_carries_settings(sched):
    post = make_post(text="t", gif_name="cat.gif", gif_transform=False, sleep_time=5)
    sched.schedule(post, "2099-01-01", "2099-01-01", ["09:00"])
    job = sched.store.load_jobs()[0]
    assert job["post_data"]["gif_transform"] is False
    assert job["post_data"]["gif_name"] == "cat.gif"
    assert job["sleep_time"] == 5


def test_plan_content_stored_once(sched):
    # 200 jobs must not serialize the photo list per job
    post = make_post(photo_paths=[f"p{i}.jpg" for i in range(200)],
                     different_posts=True)
    sched.schedule(post, "2099-01-01", "2099-01-01", ["09:00"])
    with open(sched.store.path, encoding="utf-8") as f:
        doc = json.load(f)
    assert doc["post_data"]["photo_paths"][0] == "p0.jpg"
    assert all("post_data" not in row for row in doc["jobs"])


def test_different_posts_hand_out_photos_in_order(sched):
    post = make_post(photo_paths=["a.jpg", "b.jpg", "c.jpg"], different_posts=True)
    # 6 slots, only 3 photos: scheduling stops early
    ok, _ = sched.schedule(post, "2099-01-01", "2099-01-02",
                           ["09:00", "12:00", "18:00"])
    assert ok is True
    jobs = sched.store.load_jobs()
    assert len(jobs) == 3
    assert [j["photo_index"] for j in jobs] == [0, 1, 2]
    assert sched.store.get_rotation(ROTATION_KEY) == 2
    assert all(j["token_name"] == "t1" and j["group_name"] == "g1" for j in jobs)


def test_same_photo_for_every_slot(sched):
    sched.schedule(make_post(photo_paths=["one.jpg"]),
                   "2099-01-01", "2099-01-02", ["09:00"])
    jobs = sched.store.load_jobs()
    assert len(jobs) == 2
    assert all("photo_index" not in j for j in jobs)


def test_legacy_plan_with_single_photo_path(sched):
    # pre-1.2 plans keep photo_path instead of a list
    job = {"post_time": "2099-01-01 09:00", "attempt": 0,
           "token_name": "t1", "group_name": "g1",
           "post_data": {"text": "t", "photo_path": "old.jpg"}}
    sched.store.save_jobs([job])
    loaded = sched.store.load_jobs()[0]
    assert PostScheduler._media_for(loaded, loaded["post_data"]) == "old.jpg"
    info = sched.current_jobs()[0]
    assert info["photo"] == "old.jpg"


def test_rotation_restarts_for_new_plan(sched):
    post = make_post(photo_paths=["a.jpg"], different_posts=True)
    sched.schedule(post, "2099-01-01", "2099-01-01", ["09:00"])
    assert sched.store.get_rotation(ROTATION_KEY) == 0
    sched.schedule(post, "2099-01-02", "2099-01-02", ["09:00"])
    assert sched.store.load_jobs()[0]["photo_index"] == 0


def test_cancel_job(sched):
    sched.schedule(make_post(), "2099-01-01", "2099-01-01", ["09:00"])
    assert sched.cancel_job("2099-01-01 09:00") is True
    assert sched.cancel_job("2099-01-01 09:00") is False
    assert sched.store.pending_count() == 0


def test_execute_uploads_and_posts(sched, tmp_path):
    first = tmp_path / "a.jpg"
    second = tmp_path / "b.jpg"
    first.write_bytes(b"x")
    second.write_bytes(b"x")
    client = RecordingClient()
    sched.client = client

    post = make_post(photo_paths=[str(first), str(second)], different_posts=True)
    sched.schedule(post, "2099-01-01", "2099-01-01", ["09:00", "12:00"])
    jobs = sched.store.load_jobs()
    sched._execute(jobs[0])
    sched._execute(jobs[1])

    assert [c[0] for c in client.calls] == ["photo", "post", "photo", "post"]
    assert client.calls[0][1] == str(first)
    assert client.calls[2][1] == str(second)
    # the group id, the message, a future publish time
    assert client.calls[1][1] == "42"
    assert client.calls[1][2] == "hello"
    assert client.calls[1][4] > int(datetime.now().timestamp())


def test_execute_routes_gif_with_its_options(sched, tmp_path):
    gif = tmp_path / "cat.gif"
    gif.write_bytes(b"GIF89a")
    client = RecordingClient()
    sched.client = client

    sched.schedule(
        make_post(photo_paths=[str(gif)], gif_name="cat", gif_transform=False),
        "2099-01-01", "2099-01-01", ["09:00"])
    sched._execute(sched.store.load_jobs()[0])

    assert client.calls[0] == ("gif", str(gif), "42", "cat", False)


def test_execute_rejects_past_publish_time(sched):
    sched.client = RecordingClient()
    ok, _ = sched.schedule(make_post(), "2020-01-01", "2020-01-01", ["09:00"])
    assert ok is True
    with pytest.raises(PublishTimeInPastError):
        sched._execute(sched.store.load_jobs()[0])


def test_permanent_errors_fail_without_retry():
    assert PostScheduler._is_permanent(PublishTimeInPastError("past")) is True
    assert PostScheduler._is_permanent(FileNotFoundError("gone.jpg")) is True
    assert PostScheduler._is_permanent(ValueError("bad file type")) is True
    assert PostScheduler._is_permanent(ClientError("bad token", permanent=True)) is True
    assert PostScheduler._is_permanent(ClientError("rate limited")) is False
    assert PostScheduler._is_permanent(RuntimeError("network flake")) is False
