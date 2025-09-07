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


