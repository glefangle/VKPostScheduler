from datetime import datetime

import pytest
from vk_api.exceptions import ApiError

from job_store import JobStore
from scheduler import (
    PERMANENT_VK_CODES,
    ROTATION_KEY,
    PostData,
    PostScheduler,
    PublishTimeInPastError,
)
from vk_config import MemoryStore, VKConfigManager, VKGroup


@pytest.fixture
def sched(tmp_path, monkeypatch):
    cfg = VKConfigManager(str(tmp_path / "vk_config.json"), MemoryStore())
    cfg.add_token("t1", "secret")
    cfg.get_token("t1").add_group(VKGroup("g1", "42"))
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
    cfg = VKConfigManager(str(tmp_path / "c.json"), MemoryStore())
    s = PostScheduler(config=cfg, store=JobStore(str(tmp_path / "j.json")))
    problem = s.validate(make_post(), "2026-01-01", "2026-01-01", ["09:00"])
    assert "token" in problem.lower()


def test_validate_no_group(sched):
    sched.config.set_selection("t1", None)
    problem = sched.validate(make_post(), "2026-01-01", "2026-01-01", ["09:00"])
    assert "group" in problem.lower()


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
