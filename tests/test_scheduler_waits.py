"""Condition-based waits: a state change must wake the waiter at once."""

import threading
import time
from datetime import date

import pytest

from vkpostscheduler.schedule_time import format_time, job_key, parse_time

# generous margins: only the wake-up lower bound matters
WAKEUP = 0.05
# a state change must end a wait well under a second
WAKEUP_BUDGET = 0.45


@pytest.fixture
def sched(make_sched):
    return make_sched()


def test_next_job_waits_for_a_put_and_wakes_immediately(sched):
    def put_later():
        time.sleep(WAKEUP)
        sched._enqueue([{"post_time": "2099-01-01 09:00"}])

    threading.Thread(target=put_later).start()
    started = time.monotonic()
    job = sched._next_job()
    elapsed = time.monotonic() - started

    assert job is not None
    assert job["post_time"] == "2099-01-01 09:00"
    assert elapsed < WAKEUP_BUDGET


def test_next_job_wakes_on_stop(sched):
    threading.Timer(WAKEUP, sched.stop).start()
    started = time.monotonic()

    assert sched._next_job() is None
    assert time.monotonic() - started < WAKEUP_BUDGET


def test_next_job_takes_nothing_while_paused(sched):
    sched._enqueue([{"post_time": "2099-01-01 09:00"}])
    sched.pause()
    threading.Timer(WAKEUP, lambda: sched._set_paused(False)).start()
    started = time.monotonic()
    job = sched._next_job()
    elapsed = time.monotonic() - started

    assert job is not None
    assert elapsed >= WAKEUP * 0.5  # it did wait for the resume


def test_resume_ends_the_error_wait_immediately(sched):
    sched.pause()
    threading.Timer(WAKEUP, lambda: sched._set_paused(False)).start()
    started = time.monotonic()

    assert sched._wait_while_paused(30) == "resumed"
    assert time.monotonic() - started < WAKEUP_BUDGET


def test_error_wait_times_out_while_still_paused(sched):
    sched.pause()
    started = time.monotonic()

    assert sched._wait_while_paused(0.2) == "ok"
    assert time.monotonic() - started >= 0.2


def test_stop_interrupts_the_error_wait(sched):
    sched.pause()
    threading.Timer(WAKEUP, sched.stop).start()
    started = time.monotonic()

    assert sched._wait_while_paused(30) == "stopped"
    assert time.monotonic() - started < WAKEUP_BUDGET


def test_backoff_freezes_while_paused(sched):
    # 0.25 s of the countdown must stay frozen
    threading.Timer(0.1, sched.pause).start()
    threading.Timer(0.35, lambda: sched._set_paused(False)).start()
    started = time.monotonic()

    assert sched._wait_out_backoff(0.5) == "ok"
    elapsed = time.monotonic() - started
    assert elapsed >= 0.7


def test_backoff_wakes_on_stop(sched):
    threading.Timer(WAKEUP, sched.stop).start()
    started = time.monotonic()

    assert sched._wait_out_backoff(30) == "stopped"
    assert time.monotonic() - started < WAKEUP_BUDGET


def test_sleep_between_posts_is_cut_short_by_pause_or_stop(sched):
    started = time.monotonic()
    sched.pause()
    sched._sleep_between_posts(30)
    assert time.monotonic() - started < WAKEUP_BUDGET

    threading.Timer(WAKEUP, sched.stop).start()
    started = time.monotonic()
    sched._sleep_between_posts(30)
    assert time.monotonic() - started < WAKEUP_BUDGET


def test_worker_consumes_a_full_plan_without_polling(sched):
    """Enqueue, drain _next_job, then block and wake on stop."""
    sched._enqueue([{"post_time": "2099-01-01 09:00"},
                    {"post_time": "2099-01-01 10:00"}])
    first = sched._next_job()
    second = sched._next_job()
    assert [j["post_time"] for j in (first, second)] == \
        ["2099-01-01 09:00", "2099-01-01 10:00"]

    threading.Timer(WAKEUP, sched.stop).start()
    started = time.monotonic()
    assert sched._next_job() is None
    assert time.monotonic() - started < WAKEUP_BUDGET


def test_sleep_between_posts_zero_is_a_noop(sched):
    started = time.monotonic()
    sched._sleep_between_posts(0)
    assert time.monotonic() - started < 0.05


def test_time_objects_round_trip_through_the_job_key():
    t = parse_time("9:05")
    assert format_time(t) == "09:05"
    assert job_key(date(2099, 1, 2), t) == "2099-01-02 09:05"
    with pytest.raises(ValueError):
        parse_time("25:00")
    with pytest.raises(ValueError):
        parse_time("9am")
