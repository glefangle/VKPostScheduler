import json

from vkpostscheduler.job_store import JobStore


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


def test_set_attempt_updates_only_the_matching_row(tmp_path):
    store = JobStore(str(tmp_path / "jobs.json"))
    store.add_jobs([make_job("2026-10-01 09:00"), make_job("2026-10-01 10:00")])
    assert store.set_attempt("2026-10-01 09:00", 2) is True
    assert [j["attempt"] for j in store.load_jobs()] == [2, 0]
    assert store.set_attempt("2026-10-01 11:00", 1) is False


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


def test_rotation_survives_job_rewrites(tmp_path):
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


def test_shared_post_data_stored_once_and_rehydrated(tmp_path):
    store = JobStore(str(tmp_path / "jobs.json"))
    shared = {"text": "hi", "photo_paths": [f"p{i}.jpg" for i in range(200)]}
    store.add_jobs([make_job(f"2026-10-01 09:{m:02d}") for m in range(10)],
                   post_data=shared)

    doc = json.loads((tmp_path / "jobs.json").read_text(encoding="utf-8"))
    assert doc["post_data"]["text"] == "hi"
    assert all("post_data" not in row for row in doc["jobs"])

    loaded = store.load_jobs()
    assert all(j["post_data"]["text"] == "hi" for j in loaded)
    # each job gets its own copy of the shared dict
    assert loaded[0]["post_data"] is not loaded[1]["post_data"]


def test_legacy_jobs_keep_own_post_data(tmp_path):
    # files written by older versions carry post_data inside every job
    path = tmp_path / "jobs.json"
    job = make_job("2026-10-01 09:00",
                   post_data={"text": "old", "photo_paths": ["x.jpg"]})
    path.write_text(json.dumps({"jobs": [job]}), encoding="utf-8")
    store = JobStore(str(path))
    assert store.load_jobs()[0]["post_data"]["text"] == "old"


def test_clear_jobs_drops_shared_post_data(tmp_path):
    store = JobStore(str(tmp_path / "jobs.json"))
    store.add_jobs([make_job("2026-10-01 09:00")], post_data={"text": "hi"})
    store.clear_jobs()
    doc = json.loads((tmp_path / "jobs.json").read_text(encoding="utf-8"))
    assert "post_data" not in doc


def test_rereads_file_changed_externally(tmp_path):
    path = tmp_path / "jobs.json"
    store = JobStore(str(path))
    store.add_jobs([make_job("2026-10-01 09:00")])
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["jobs"].append(make_job("2026-10-01 10:00"))
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert store.pending_count() == 2
