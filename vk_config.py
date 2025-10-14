"""Token/target configuration; secrets live in the OS credential store."""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class VKGroup:
    name: str
    group_id: str
    day_schedule: List[str] = field(default_factory=list)
    default_text: str = ""

    def __post_init__(self):
        # group ids are numbers, possibly negative
        try:
            int(str(self.group_id).lstrip("-"))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid group ID '{self.group_id}': must be a number")
        if self.day_schedule is None:
            self.day_schedule = []


@dataclass
class VKToken:
    name: str
    groups: List[VKGroup] = field(default_factory=list)

    def __post_init__(self):
        if self.groups is None:
            self.groups = []

    def add_group(self, group: VKGroup) -> None:
        if any(g.name == group.name for g in self.groups):
            raise ValueError(f"Group '{group.name}' already exists")
        self.groups.append(group)

    def remove_group(self, name: str) -> bool:
        for i, g in enumerate(self.groups):
            if g.name == name:
                del self.groups[i]
                return True
        return False

    def get_group(self, name: str) -> Optional[VKGroup]:
        for g in self.groups:
            if g.name == name:
                return g
        return None

    def update_group(self, old_name: str, new_group: VKGroup) -> bool:
        for i, g in enumerate(self.groups):
            if g.name == old_name:
                self.groups[i] = new_group
                return True
        return False


class VKConfigManager:
    def __init__(self, config_file: str = "vk_config.json"):
        self.config_file = config_file
        self.tokens: Dict[str, VKToken] = {}
        self._secrets: Dict[str, str] = {}
        self.selected_token: Optional[str] = None
        self.selected_group: Optional[str] = None
        self.load()

    # -- tokens ------------------------------------------------------------

    def add_token(self, name: str, value: str) -> None:
        if name in self.tokens:
            raise ValueError(f"Token '{name}' already exists")
        self._secrets[name] = value
        self.tokens[name] = VKToken(name=name)
        self.save()

    def update_token(self, old_name: str, new_name: str, new_value: Optional[str] = None) -> None:
        if old_name not in self.tokens:
            raise ValueError(f"Token '{old_name}' not found")
        if old_name != new_name:
            if new_name in self.tokens:
                raise ValueError(f"Token '{new_name}' already exists")

        if new_value is not None:
            self._secrets[new_name] = new_value
            if old_name != new_name:
                self._secrets.pop(old_name, None)
        elif old_name != new_name:
            if old_name not in self._secrets:
                raise ValueError(f"Token value for '{old_name}' is missing")
            self._secrets[new_name] = self._secrets.pop(old_name)

        token = self.tokens.pop(old_name)
        token.name = new_name
        self.tokens[new_name] = token
        if self.selected_token == old_name:
            self.selected_token = new_name
        self.save()

    def remove_token(self, name: str) -> bool:
        if name not in self.tokens:
            return False
        del self.tokens[name]
        self._secrets.pop(name, None)
        if self.selected_token == name:
            self.selected_token = None
            self.selected_group = None
        self.save()
        return True

    def get_token(self, name: str) -> Optional[VKToken]:
        return self.tokens.get(name)

    def token_names(self) -> List[str]:
        return list(self.tokens)

    def group_names(self, token_name: str) -> List[str]:
        token = self.tokens.get(token_name)
        return [g.name for g in token.groups] if token else []

    def token_value(self, name: str) -> Optional[str]:
        if name not in self.tokens:
            return None
        return self._secrets.get(name)

    # -- selection ---------------------------------------------------------

    def set_selection(self, token_name: Optional[str], group_name: Optional[str] = None) -> None:
        if token_name and token_name not in self.tokens:
            raise ValueError(f"Token '{token_name}' not found")
        if token_name and group_name:
            token = self.tokens[token_name]
            if not token.get_group(group_name):
                raise ValueError(f"Group '{group_name}' not found in token '{token_name}'")
        self.selected_token = token_name
        self.selected_group = group_name
        self.save()

    def get_selection(self):
        return self.selected_token, self.selected_group

    def has_valid_selection(self) -> bool:
        return (
            self.selected_token is not None
            and self.selected_group is not None
            and self.token_value(self.selected_token) is not None
            and self.selected_group_id() is not None
        )

    def selected_token_value(self) -> Optional[str]:
        return self.token_value(self.selected_token) if self.selected_token else None

    def selected_group_id(self) -> Optional[str]:
        token = self.tokens.get(self.selected_token) if self.selected_token else None
        if not token or not self.selected_group:
            return None
        group = token.get_group(self.selected_group)
        return group.group_id if group else None

    # -- per-group schedule and default text -------------------------------

    def get_group_schedule(self, token_name: str, group_name: str) -> List[str]:
        token = self.tokens.get(token_name)
        group = token.get_group(group_name) if token else None
        return list(group.day_schedule) if group else []

    def set_group_schedule(self, token_name: str, group_name: str, schedule: List[str]) -> None:
        group = self._group_or_raise(token_name, group_name)
        for t in schedule:
            self._check_time(t)
        group.day_schedule = list(schedule)
        self.save()

    def get_group_default_text(self, token_name: str, group_name: str) -> str:
        group = self._find_group(token_name, group_name)
        return group.default_text if group else ""

    def set_group_default_text(self, token_name: str, group_name: str, text: str) -> None:
        group = self._group_or_raise(token_name, group_name)
        group.default_text = text
        self.save()

    def _find_group(self, token_name, group_name):
        token = self.tokens.get(token_name)
        return token.get_group(group_name) if token else None

    def _group_or_raise(self, token_name, group_name):
        group = self._find_group(token_name, group_name)
        if not group:
            raise ValueError(f"Group '{group_name}' not found in token '{token_name}'")
        return group

    @staticmethod
    def _check_time(t: str) -> None:
        try:
            h, m = t.split(":")
            assert 0 <= int(h) <= 23 and 0 <= int(m) <= 59
        except (ValueError, IndexError, AssertionError):
            raise ValueError(f"Bad time '{t}', expected HH:MM")

    # -- persistence ---------------------------------------------------------

    def load(self) -> None:
        if not os.path.exists(self.config_file):
            self.save()
            return

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.error("config %s is unreadable: %s", self.config_file, e)
            self.tokens = {}
            self._secrets = {}
            self.selected_token = None
            self.selected_group = None
            self.save()
            return

        self.tokens = {}
        self._secrets = {}
        for name, tok in data.get("tokens", {}).items():
            groups = [VKGroup(**g) for g in tok.get("groups", [])]
            self.tokens[name] = VKToken(name=name, groups=groups)
            if "token" in tok:
                self._secrets[name] = tok["token"]

        self.selected_token = data.get("selected_token")
        self.selected_group = data.get("selected_group")
        if self.selected_token and self.selected_token not in self.tokens:
            self.selected_token = None
            self.selected_group = None

        self.save()

    def save(self) -> None:
        data = {
            "tokens": {
                name: {
                    "token": self._secrets.get(name, ""),
                    "groups": [
                        {"name": g.name, "group_id": g.group_id,
                         "day_schedule": g.day_schedule, "default_text": g.default_text}
                        for g in tok.groups
                    ],
                }
                for name, tok in self.tokens.items()
            },
            "selected_token": self.selected_token,
            "selected_group": self.selected_group,
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
