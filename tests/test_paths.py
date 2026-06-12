import paths


def test_migration_moves_legacy_files(tmp_path, monkeypatch):
    (tmp_path / "vk_config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "jobs_state.json").write_text("{}", encoding="utf-8")
    (tmp_path / "error.log").write_text("x", encoding="utf-8")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "app.log").write_text("x", encoding="utf-8")

    target = tmp_path / "data"
    monkeypatch.setattr(paths, "data_dir", lambda: str(target))
    monkeypatch.chdir(tmp_path)

    paths.migrate_legacy_files()

    assert (target / "vk_config.json").exists()
    assert (target / "jobs_state.json").exists()
    assert (target / "error.log").exists()
    assert (target / "logs" / "app.log").exists()
    assert not (tmp_path / "vk_config.json").exists()
    assert not (tmp_path / "logs").exists()


def test_migration_never_overwrites_data_dir_files(tmp_path, monkeypatch):
    target = tmp_path / "data"
    target.mkdir()
    (target / "vk_config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "vk_config.json").write_text("old", encoding="utf-8")

    monkeypatch.setattr(paths, "data_dir", lambda: str(target))
    monkeypatch.chdir(tmp_path)

    paths.migrate_legacy_files()

    assert (target / "vk_config.json").read_text(encoding="utf-8") == "{}"
    # the unread copy stays where it was
    assert (tmp_path / "vk_config.json").read_text(encoding="utf-8") == "old"


def test_migration_without_legacy_files(tmp_path, monkeypatch):
    target = tmp_path / "data"
    monkeypatch.setattr(paths, "data_dir", lambda: str(target))
    monkeypatch.chdir(tmp_path)

    paths.migrate_legacy_files()

    assert target.is_dir()
    assert list(target.iterdir()) == []
