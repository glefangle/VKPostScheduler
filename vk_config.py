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

    def __post_init__(self):
        # group ids are numbers, possibly negative
        try:
            int(str(self.group_id).lstrip("-"))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid group ID '{self.group_id}': must be a number")


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

