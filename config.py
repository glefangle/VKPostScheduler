"""Token/target configuration; secrets live in the OS credential store."""

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

import keyring

import jsonio

log = logging.getLogger(__name__)

DEFAULT_KEYRING_SERVICE = "PostScheduler"
CONFIG_VERSION = 2


class ConfigError(Exception):
    pass


class SecretStore(Protocol):
    """Token value storage: keyring in production, memory in tests."""

    def get(self, name: str) -> str | None: ...

    def set(self, name: str, secret: str) -> None: ...

    def delete(self, name: str) -> None: ...


class KeyringStore:
    """Secret storage backed by the OS credential store."""

    def __init__(self, service: str = DEFAULT_KEYRING_SERVICE):
        self.service = service

    def get(self, name: str) -> str | None:
        try:
            return keyring.get_password(self.service, name)
        except keyring.errors.KeyringError as e:
            raise ConfigError(f"Cannot read token '{name}' from the credential store: {e}") from e

    def set(self, name: str, secret: str) -> None:
        try:
            keyring.set_password(self.service, name, secret)
        except keyring.errors.KeyringError as e:
            raise ConfigError(f"Cannot save token '{name}' to the credential store: {e}") from e

    def delete(self, name: str) -> None:
        try:
            keyring.delete_password(self.service, name)
        except keyring.errors.KeyringError:
            # deleting a missing entry is fine
            log.debug("keyring delete failed for %s", name, exc_info=True)


class MemoryStore:
    """In-memory store, used by tests."""

    def __init__(self):
        self.secrets: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.secrets.get(name)

    def set(self, name: str, secret: str) -> None:
        self.secrets[name] = secret

    def delete(self, name: str) -> None:
        self.secrets.pop(name, None)


@dataclass
class Group:
    """One posting target: display name plus raw platform id."""

    name: str
    group_id: str
    day_schedule: list[str] = field(default_factory=list)
    default_text: str = ""

    def __post_init__(self):
        if not str(self.group_id).strip():
            raise ValueError("Group id must not be empty")
        if self.day_schedule is None:
            self.day_schedule = []


@dataclass
class Token:
    name: str
    groups: list[Group] = field(default_factory=list)

    def __post_init__(self):
        # tolerate groups loaded from the old json format
        if self.groups and isinstance(self.groups[0], dict):
            raw: list[Any] = cast(list[Any], self.groups)
            self.groups = [Group(**g) for g in raw]
        elif self.groups is None:
            self.groups = []

    def add_group(self, group: Group) -> None:
        if any(g.name == group.name for g in self.groups):
            raise ValueError(f"Group '{group.name}' already exists")
        self.groups.append(group)

    def remove_group(self, name: str) -> bool:
        for i, g in enumerate(self.groups):
            if g.name == name:
                del self.groups[i]
                return True
        return False

    def get_group(self, name: str) -> Group | None:
        for g in self.groups:
            if g.name == name:
                return g
        return None

    def update_group(self, old_name: str, new_group: Group) -> bool:
        for i, g in enumerate(self.groups):
            if g.name == old_name:
                if any(other.name == new_group.name for other in self.groups if other is not g):
                    raise ValueError(f"Group '{new_group.name}' already exists")
                self.groups[i] = new_group
                return True
        return False


class ConfigManager:
    def __init__(self, config_file: str, secrets: SecretStore | None = None,
                 service_name: str = DEFAULT_KEYRING_SERVICE):
        # namespaces credential-store entries between apps
        self.config_file = config_file
        self.secrets: SecretStore = secrets or KeyringStore(service_name)
        self.tokens: dict[str, Token] = {}
        self.selected_token: str | None = None
        self.selected_group: str | None = None
        self.load()

    # -- tokens ------------------------------------------------------------

    def add_token(self, name: str, value: str) -> None:
        if name in self.tokens:
            raise ValueError(f"Token '{name}' already exists")
        self.secrets.set(name, value)
        self.tokens[name] = Token(name=name)
        self.save()

    def update_token(self, old_name: str, new_name: str, new_value: str | None = None) -> None:
        if old_name not in self.tokens:
            raise ValueError(f"Token '{old_name}' not found")
        if old_name != new_name:
            if new_name in self.tokens:
                raise ValueError(f"Token '{new_name}' already exists")

        if new_value is not None:
            self.secrets.set(new_name, new_value)
            if old_name != new_name:
                self.secrets.delete(old_name)
        elif old_name != new_name:
            # rename only: rehang the secret under the new name
            value = self.secrets.get(old_name)
            if value is None:
                raise ConfigError(f"Token value for '{old_name}' is missing "
                                  f"from the credential store")
            self.secrets.set(new_name, value)
            self.secrets.delete(old_name)

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
        self.secrets.delete(name)
        if self.selected_token == name:
            self.selected_token = None
            self.selected_group = None
        self.save()
        return True

    def get_token(self, name: str) -> Token | None:
        return self.tokens.get(name)

    def token_names(self) -> list[str]:
        return list(self.tokens)

    def group_names(self, token_name: str) -> list[str]:
        token = self.tokens.get(token_name)
        return [g.name for g in token.groups] if token else []

    def token_value(self, name: str) -> str | None:
        if name not in self.tokens:
            return None
        return self.secrets.get(name)

    # -- selection ---------------------------------------------------------

    def set_selection(self, token_name: str | None, group_name: str | None = None) -> None:
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

    def selected_token_value(self) -> str | None:
        return self.token_value(self.selected_token) if self.selected_token else None

    def selected_group_id(self) -> str | None:
        token = self.tokens.get(self.selected_token) if self.selected_token else None
        if not token or not self.selected_group:
            return None
        group = token.get_group(self.selected_group)
        return group.group_id if group else None

    # -- per-group schedule and default text -------------------------------

    def get_group_schedule(self, token_name: str, group_name: str) -> list[str]:
        token = self.tokens.get(token_name)
        group = token.get_group(group_name) if token else None
        return list(group.day_schedule) if group else []

    def set_group_schedule(self, token_name: str, group_name: str, schedule: list[str]) -> None:
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
            hour, minute = int(h), int(m)
        except (ValueError, AttributeError):
            raise ValueError(f"Bad time '{t}', expected HH:MM") from None
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Bad time '{t}', expected HH:MM")

    # -- persistence ---------------------------------------------------------

    def load(self) -> None:
        data = jsonio.read_json(self.config_file)

        tokens_data = data.get("tokens", {})
        migrated = False
        self.tokens = {}
        for name, tok in tokens_data.items():
            try:
                if "token" in tok:  # pre-keyring format, move the secret out
                    self.secrets.set(name, tok["token"])
                    del tok["token"]
                    migrated = True
                groups = [Group(**g) for g in tok.get("groups", [])]
                self.tokens[name] = Token(name=name, groups=groups)
            except (TypeError, ValueError) as e:
                # one bad entry shouldn't sink the rest
                log.error("skipping malformed token %r: %s", name, e)

        self.selected_token = data.get("selected_token")
        self.selected_group = data.get("selected_group")
        if self.selected_token and self.selected_token not in self.tokens:
            self.selected_token = None
            self.selected_group = None

        if migrated:
            log.info("moved stored tokens into the OS credential store")

        self.save()

    def save(self) -> None:
        data = {
            "version": CONFIG_VERSION,
            "tokens": {
                name: {"groups": [
                    {"name": g.name, "group_id": g.group_id,
                     "day_schedule": g.day_schedule, "default_text": g.default_text}
                    for g in tok.groups
                ]}
                for name, tok in self.tokens.items()
            },
            "selected_token": self.selected_token,
            "selected_group": self.selected_group,
        }
        jsonio.write_json(self.config_file, data, indent=2)
