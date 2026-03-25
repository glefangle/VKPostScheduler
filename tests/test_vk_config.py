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


def test_v1_migration_moves_token_into_store(tmp_path):
    path = tmp_path / "vk_config.json"
    path.write_text(json.dumps({
        "tokens": {"old": {
            "name": "old",
            "token": "v1secret",
            "groups": [{"name": "g", "group_id": "123",
                        "day_schedule": ["10:00"], "default_text": "hi"}],
        }},
        "selected_token": "old",
        "selected_group": "g",
    }), encoding="utf-8")

    cfg = VKConfigManager(str(path), MemoryStore())
    assert cfg.token_value("old") == "v1secret"
    assert "v1secret" not in path.read_text(encoding="utf-8")
    assert cfg.selected_group_id() == "123"
    assert cfg.get_group_schedule("old", "g") == ["10:00"]


def test_broken_config_backed_up(tmp_path):
    path = tmp_path / "vk_config.json"
    path.write_text("{not json", encoding="utf-8")
    VKConfigManager(str(path), MemoryStore())
    assert (tmp_path / "vk_config.json.corrupt.bak").read_text(encoding="utf-8") == "{not json"
    assert read_json(path)["tokens"] == {}


def test_malformed_token_skipped(tmp_path):
    path = tmp_path / "vk_config.json"
    path.write_text(json.dumps({
        "tokens": {
            "bad": {"name": "bad", "groups": "not-a-list"},
            "good": {"name": "good", "groups": []},
        },
    }), encoding="utf-8")
    cfg = VKConfigManager(str(path), MemoryStore())
    assert cfg.token_names() == ["good"]


def test_group_schedule_time_validation(cfg):
    cfg.add_token("t", "v")
    cfg.get_token("t").add_group(VKGroup("g", "42"))
    with pytest.raises(ValueError):
        cfg.set_group_schedule("t", "g", ["25:00"])
    with pytest.raises(ValueError):
        cfg.set_group_schedule("t", "g", ["abc"])
    cfg.set_group_schedule("t", "g", ["09:30", "21:00"])
    assert cfg.get_group_schedule("t", "g") == ["09:30", "21:00"]


def test_group_name_conflicts(cfg):
    cfg.add_token("t", "v")
    token = cfg.get_token("t")
    token.add_group(VKGroup("a", "1"))
    with pytest.raises(ValueError):
        token.add_group(VKGroup("a", "2"))
    token.add_group(VKGroup("b", "2"))
    # renaming a onto the existing name b must be rejected
    with pytest.raises(ValueError):
        token.update_group("a", VKGroup("b", "3"))
    assert token.update_group("a", VKGroup("c", "3")) is True


def test_group_id_must_be_numeric():
    with pytest.raises(ValueError):
        VKGroup("bad", "club123")
