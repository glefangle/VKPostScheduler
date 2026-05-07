from datetime import datetime

import pytest

from job_store import JobStore
from posting_client import ClientError, PublishTimeInPastError
from scheduler import (
    ROTATION_KEY,
    PostData,
    PostScheduler,
)
from config import Group, ConfigManager, MemoryStore


@pytest.fixture
def sched(tmp_path, monkeypatch):
    cfg = ConfigManager(str(tmp_path / "config.json"), MemoryStore())
    cfg.add_token("t1", "secret")
    cfg.get_token("t1").add_group(Group("g1", "42"))
    cfg.set_selection("t1", "g1")

    s = PostScheduler(config=cfg, store=JobStore(str(tmp_path / "jobs.json")))
    # keep the real worker thread out of the tests
    monkeypatch.setattr(s, "ensure_worker", lambda: None)
    return s


def make_post(**kw):
    defaults = dict(text="hello", photo_paths=[], different_posts=False)
    defaults.update(kw)
    return PostData(**defaults)



def test_validate_no_token(tmp_path):
    cfg = ConfigManager(str(tmp_path / "c.json"), MemoryStore())
    s = PostScheduler(config=cfg, store=JobStore(str(tmp_path / "j.json")))
    problem = s.validate(make_post(), "2026-01-01", "2026-01-01", ["09:00"])
    assert "token" in problem.lower()


def test_validate_no_group(sched):
    sched.config.set_selection("t1", None)
    problem = sched.validate(make_post(), "2026-01-01", "2026-01-01", ["09:00"])
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



def test_build_jobs_different_posts(sched):
    post = make_post(photo_paths=["a.jpg", "b.jpg", "c.jpg"], different_posts=True)
    jobs, exhausted = sched._build_jobs(post, "2099-01-01", "2099-01-02",
                                        ["09:00", "12:00", "18:00"], "t1", "g1")
    assert len(jobs) == 3
    assert exhausted is True
    assert [j["photo_index"] for j in jobs] == [0, 1, 2]
    assert sched.store.get_rotation(ROTATION_KEY) == 2
    assert all(j["token_name"] == "t1" and j["group_name"] == "g1" for j in jobs)


def test_build_jobs_normal_mode(sched):
    post = make_post(photo_path="one.jpg")
    jobs, exhausted = sched._build_jobs(post, "2099-01-01", "2099-01-02", ["09:00"],
                                        "t1", "g1")
    assert len(jobs) == 2
    assert exhausted is False
    assert all("photo_index" not in j for j in jobs)


def test_build_jobs_carries_settings(sched):
    post = make_post(text="t", gif_name="cat.gif", gif_transform=False, sleep_time=5)
    jobs, _ = sched._build_jobs(post, "2099-01-01", "2099-01-01", ["09:00"], "t1", "g1")
    job = jobs[0]
    assert job["post_data"]["gif_transform"] is False
    assert job["post_data"]["gif_name"] == "cat.gif"
    assert job["sleep_time"] == 5
    assert job["generation"] == sched._generation


def test_execute_passes_metadata_to_client(sched):
    captured = {}

    class RecordingClient:
        def api_for(self, credential):
            return {"ok": True}

        def upload_photo(self, api, path, target_id):
            return path

        def upload_gif(self, api, path, target_id,
                       title=None, transform=True):
            return path

        def post(self, api, target_id, message, attachment, publish_ts,
                 metadata=None):
            captured.update(target_id=target_id, message=message,
                            attachment=attachment, publish_ts=publish_ts,
                            metadata=metadata)
            return {}

    sched.client = RecordingClient()
    sched.schedule(make_post(tags=["t1", "t2"], source_url="https://s"),
                   "2099-01-01", "2099-01-01", ["09:00"])
    sched._execute(sched.store.load_jobs()[0])

    assert captured["target_id"] == "42"
    assert captured["message"] == "hello"
    assert captured["metadata"]["tags"] == ["t1", "t2"]
    assert captured["metadata"]["source_url"] == "https://s"
    assert captured["metadata"]["slug"] == ""


def test_build_jobs_carries_metadata(sched):
    post = make_post(tags=["cat", "art"], source_url="https://x.y",
                     slug="my-post", send_to_twitter=True,
                     limit_reblog_interaction=True)
    jobs, _ = sched._build_jobs(post, "2099-01-01", "2099-01-01", ["09:00"],
                                "t1", "g1")
    data = jobs[0]["post_data"]
    assert data["tags"] == ["cat", "art"]
    assert data["source_url"] == "https://x.y"
    assert data["slug"] == "my-post"
    assert data["send_to_twitter"] is True
    assert data["limit_reblog_interaction"] is True


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


def test_schedule_rotation_restarts_for_new_plan(sched):
    post = make_post(photo_paths=["a.jpg"], different_posts=True)
    sched.schedule(post, "2099-01-01", "2099-01-01", ["09:00"])
    assert sched.store.get_rotation(ROTATION_KEY) == 0
    sched.schedule(post, "2099-01-02", "2099-01-02", ["09:00"])
    jobs = sched.store.load_jobs()
    assert jobs[0]["photo_index"] == 0



def test_cancel_job_marks_and_removes(sched):
    sched.schedule(make_post(), "2099-01-01", "2099-01-01", ["09:00"])
    assert sched.cancel_job("2099-01-01 09:00") is True
    assert sched.cancel_job("2099-01-01 09:00") is False
    assert sched.store.pending_count() == 0
    assert sched._is_stale({"post_time": "2099-01-01 09:00"}) is True


def test_is_stale_generation(sched):
    fresh = {"post_time": "2099-01-01 09:00", "generation": sched._generation}
    stale = {"post_time": "2099-01-01 09:00", "generation": sched._generation - 1}
    assert sched._is_stale(fresh) is False
    assert sched._is_stale(stale) is True



def test_publish_ts_future(sched):
    ts = sched._publish_ts("2099-01-01 09:00")
    assert ts > int(datetime.now().timestamp())


def test_publish_ts_past(sched):
    with pytest.raises(PublishTimeInPastError):
        sched._publish_ts("2020-01-01 09:00")



def test_permanent_client_errors():
    # the backend already decided whether retrying makes sense
    assert PostScheduler._is_permanent(ClientError("bad token", permanent=True)) is True
    assert PostScheduler._is_permanent(ClientError("rate limited")) is False


def test_permanent_non_client_errors():
    assert PostScheduler._is_permanent(PublishTimeInPastError("past")) is True
    assert PostScheduler._is_permanent(FileNotFoundError("gone.jpg")) is True
    assert PostScheduler._is_permanent(ValueError("bad file type")) is True
    assert PostScheduler._is_permanent(RuntimeError("network flake")) is False


def test_media_for_prefers_photo_index(sched):
    post_data = {"photo_paths": ["a.jpg", "b.jpg"], "photo_path": "a.jpg"}
    assert sched._media_for({"photo_index": 1}, post_data) == "b.jpg"
    assert sched._media_for({}, post_data) == "a.jpg"
    assert sched._media_for({"photo_index": 9}, post_data) == "a.jpg"
