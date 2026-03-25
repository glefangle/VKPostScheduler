import json

import pytest

from vk_config import MemoryStore, VKConfigManager, VKGroup


@pytest.fixture
def cfg(tmp_path):
    return VKConfigManager(str(tmp_path / "vk_config.json"), MemoryStore())


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_add_and_read_token(tmp_path, cfg):
    cfg.add_token("main", "secret123")
    assert cfg.token_value("main") == "secret123"
    # the json must hold metadata only, never the secret
    assert "secret123" not in (tmp_path / "vk_config.json").read_text(encoding="utf-8")
    assert "main" in read_json(tmp_path / "vk_config.json")["tokens"]


def test_duplicate_token_name(cfg):
    cfg.add_token("main", "a")
    with pytest.raises(ValueError):
        cfg.add_token("main", "b")


def test_rename_token_moves_secret(cfg):
    cfg.add_token("main", "secret123")
    cfg.update_token("main", "renamed")
    assert cfg.token_value("renamed") == "secret123"
    assert cfg.secrets.get("main") is None
    assert "renamed" in cfg.token_names()


def test_rename_with_new_value(cfg):
    cfg.add_token("main", "old")
    cfg.update_token("main", "main", "new")
    assert cfg.token_value("main") == "new"


def test_remove_token_deletes_secret(cfg):
    cfg.add_token("main", "secret123")
    assert cfg.remove_token("main") is True
    assert cfg.token_value("main") is None
    assert cfg.secrets.get("main") is None
    assert cfg.remove_token("main") is False


def test_selection_requires_existing_entries(cfg):
    with pytest.raises(ValueError):
        cfg.set_selection("nope")
    cfg.add_token("t", "v")
    cfg.get_token("t").add_group(VKGroup("g", "42"))
    cfg.set_selection("t", "g")
    assert cfg.has_valid_selection()
    with pytest.raises(ValueError):
        cfg.set_selection("t", "missing")
