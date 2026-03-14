import json

from job_store import JobStore


def make_job(post_time, **extra):
    job = {"post_time": post_time, "attempt": 0, "token_name": "t", "group_name": "g"}
    job.update(extra)
    return job


def test_roundtrip(tmp_path):
    store = JobStore(str(tmp_path / "jobs.json"))
    jobs = [make_job("2026-10-01 09:00"), make_job("2026-10-01 12:00")]
    store.save_jobs(jobs)
    assert store.load_jobs() == jobs


def test_add_and_remove(tmp_path):
    store = JobStore(str(tmp_path / "jobs.json"))
    store.add_jobs([make_job("2026-10-01 09:00"), make_job("2026-10-01 10:00")])
    store.add_jobs([])  # no-op
    assert store.pending_count() == 2

    assert store.remove_by_post_time("2026-10-01 09:00") is True
    assert store.remove_by_post_time("2026-10-01 09:00") is False
    assert [j["post_time"] for j in store.load_jobs()] == ["2026-10-01 10:00"]

    store.clear_jobs()
    assert store.pending_count() == 0


def test_malformed_rows_dropped(tmp_path):
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps({"jobs": [
        42,
        None,
        {"post_time": ""},
        {"no_time": True},
        make_job("2026-10-01 09:00"),
    ]}), encoding="utf-8")
    store = JobStore(str(path))
    assert [j["post_time"] for j in store.load_jobs()] == ["2026-10-01 09:00"]


def test_broken_file_backed_up(tmp_path):
    path = tmp_path / "jobs.json"
    path.write_text("{broken", encoding="utf-8")
    store = JobStore(str(path))
    assert store.load_jobs() == []
    assert (tmp_path / "jobs.json.corrupt.bak").read_text(encoding="utf-8") == "{broken"


def test_rotations(tmp_path):
    store = JobStore(str(tmp_path / "jobs.json"))
    assert store.get_rotation("user_photos") == -1
    store.set_rotation("user_photos", 3)
    assert store.get_rotation("user_photos") == 3
    # rotations survive an unrelated jobs rewrite
    store.save_jobs([make_job("2026-10-01 09:00")])
    assert store.get_rotation("user_photos") == 3
    store.reset_rotation("user_photos")
    assert store.get_rotation("user_photos") == -1


def test_no_temp_files_left_behind(tmp_path):
    store = JobStore(str(tmp_path / "jobs.json"))
    store.save_jobs([make_job("2026-10-01 09:00")])
    store.set_rotation("user_photos", 0)
    assert list(tmp_path.glob("*.tmp")) == []
