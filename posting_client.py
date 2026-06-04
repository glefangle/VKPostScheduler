"""The contract every posting backend implemments."""

from abc import ABC, abstractmethod


class ClientError(Exception):
    """A platform API error; permanent=True means retrying can never help."""

    def __init__(self, message: str, permanent: bool = False, code=None):
        super().__init__(message)
        self.permanent = permanent
        self.code = code


class PublishTimeInPastError(ClientError):
    """The publish time is in the past; nothing to retry."""

    def __init__(self, message: str = "publish time has already passed"):
        super().__init__(message, permanent=True)


class PostClient(ABC):
    """What a posting backend must provide."""

    @abstractmethod
    def api_for(self, credential: str):
        """Authenticated api handle for a credential, cached."""

    @abstractmethod
    def upload_photo(self, api, path: str, target_id: str) -> str:
        """Upload one photo, return the attachment reference post() takes."""

    @abstractmethod
    def upload_gif(self, api, path: str, target_id: str,
                   title: str | None = None, transform: bool = True) -> str:
        """Upload one gif, same contract as upload_photo."""

    @abstractmethod
    def post(self, api, target_id: str, message: str | None,
             attachment: str | None, publish_ts: int | None,
             post_data: dict | None = None) -> dict:
        """Create the post; publish_ts schedules it, None posts right away."""
