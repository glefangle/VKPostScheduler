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
