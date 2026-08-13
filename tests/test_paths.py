import pytest

from vkpostscheduler import paths


@pytest.fixture
def legacy_home(tmp_path, monkeypatch):
    """An old-style install: config and logs in the cwd."""
    target = tmp_path / "data"
    monkeypatch.setattr(paths, "data_dir", lambda: str(target))
    monkeypatch.chdir(tmp_path)
    return target


def test_migration_moves_legacy_files(tmp_path, legacy_home):
    (tmp_path / "vk_config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "jobs_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "error.log").write_text("x", encoding="utf-8")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "app.log").write_text("x", encoding="utf-8")

    paths.migrate_legacy_files()

    assert (legacy_home / "vk_config.json").exists()
    assert (legacy_home / "jobs_state.json").exists()
    assert (legacy_home / "error.log").exists()
    assert (legacy_home / "logs" / "app.log").exists()
    assert not (tmp_path / "vk_config.json").exists()
    assert not (tmp_path / "logs").exists()


def test_migration_never_overwrites_data_dir_files(tmp_path, legacy_home):
    legacy_home.mkdir()
    (legacy_home / "vk_config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "vk_config.json").write_text("old", encoding="utf-8")

    paths.migrate_legacy_files()

    assert (legacy_home / "vk_config.json").read_text(encoding="utf-8") == "{}"
    # the unread copy stays where it was
    assert (tmp_path / "vk_config.json").read_text(encoding="utf-8") == "old"


def test_migration_without_legacy_files(legacy_home):
    paths.migrate_legacy_files()

    assert legacy_home.is_dir()
    assert list(legacy_home.iterdir()) == []
