"""Shared test setup: headless Qt plus a scheduler factory."""

import os

import pytest

from vkpostscheduler.config import ConfigManager, Group, MemoryStore
from vkpostscheduler.job_store import JobStore
from vkpostscheduler.scheduler import PostScheduler

# run qt headless everywhere; the package resolves via pyproject pythonpath
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def make_sched(tmp_path):
    """A PostScheduler over a throwaway config, token t1 with group g1."""

    def build():
        cfg = ConfigManager(str(tmp_path / "config.json"), MemoryStore())
        cfg.add_token("t1", "secret")
        token = cfg.get_token("t1")
        assert token is not None
        token.add_group(Group("g1", "42"))
        cfg.set_selection("t1", "g1")
        return PostScheduler(config=cfg,
                             store=JobStore(str(tmp_path / "jobs.json")))

    return build
