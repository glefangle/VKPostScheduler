"""VK posting backend: wall photo uploads, gifs as documents, wall.post."""

import logging
import os
import re
from typing import Dict, Optional

import requests
import vk_api
from vk_api.exceptions import ApiError, VkApiError

from gif_transformer import GIFTransformer
from posting_client import ClientError, PostClient

log = logging.getLogger(__name__)

UPLOAD_TIMEOUT = (10, 300)  # (connect, read); big gifs read slowly, be generous

# retrying never hepls: auth, access, blocked app, invalid params
PERMANENT_VK_CODES = {5, 7, 8, 15, 100}


class VKClient(PostClient):
    # vk crops documents outside this range; TODO: limits are reverse-engineered
    GIF_MIN_RATIO = 0.66
    GIF_MAX_RATIO = 2.5

    def __init__(self):
        self.gif = GIFTransformer(self.GIF_MIN_RATIO, self.GIF_MAX_RATIO, tag="vk")
        self._sessions: Dict[str, object] = {}

    def api_for(self, credential: str):
        """Authenticated api object per token, cached."""
        if credential not in self._sessions:
            try:
                session = vk_api.VkApi(token=credential)
                self._sessions[credential] = session.get_api()
            except VkApiError as e:
                raise self._wrap(e) from e
        return self._sessions[credential]

    def _call(self, method, **params):
        try:
            return method(**params)
        except ApiError as e:
            raise self._wrap(e) from e

    @staticmethod
    def _wrap(error: ApiError) -> ClientError:
        code = None
        err_data = getattr(error, "error", None)
        if isinstance(err_data, dict):
            code = err_data.get("error_code")
        if code is None:
            m = re.search(r"\[(\d+)\]", str(error))
            code = int(m.group(1)) if m else None
        return ClientError(str(error), permanent=code in PERMANENT_VK_CODES,
                           code=code)

    @staticmethod
    def _group_id(target_id: str) -> int:
        """Uploads take a positive id, wall.post a negative one."""
        try:
            return abs(int(str(target_id).strip()))
        except (TypeError, ValueError):
            raise ValueError(f"Invalid group ID '{target_id}': must be a number")

    # -- uploading --------------------------------------------------------

    def upload_photo(self, api, path: str, target_id: str) -> str:
        group_id = self._group_id(target_id)
        server = self._call(api.photos.getWallUploadServer, group_id=group_id)
        with open(path, "rb") as fh:
            resp = requests.post(server["upload_url"], files={"photo": fh}, timeout=UPLOAD_TIMEOUT)
        resp.raise_for_status()
        photo = resp.json()

        saved = self._call(api.photos.saveWallPhoto,
                           server=photo["server"],
                           photo=photo["photo"],
                           hash=photo["hash"],
                           group_id=group_id)[0]
        log.info("uploaded photo %s as photo%d_%d",
                 os.path.basename(path), saved["owner_id"], saved["id"])
        return f"photo{saved['owner_id']}_{saved['id']}"

    def upload_gif(self, api, path: str, target_id: str,
                   title: Optional[str] = None, transform: bool = True) -> str:
        """GIFs go up as documents."""
        group_id = self._group_id(target_id)
        actual_path = path
        temp_created = False
        if transform:
            actual_path, temp_created = self._maybe_transform(path)

        try:
            # no group_id on purpose, see the VK docs for docs.getWallUploadServer
            server = self._call(api.docs.getWallUploadServer)
            with open(actual_path, "rb") as fh:
                resp = requests.post(server["upload_url"], files={"file": fh}, timeout=UPLOAD_TIMEOUT)
            resp.raise_for_status()
            doc_data = resp.json()

            saved = self._call(api.docs.save, file=doc_data["file"],
                               title=title or os.path.basename(path))
            doc = saved["doc"]
            log.info("uploaded gif %s as doc%d_%d",
                     os.path.basename(path), doc["owner_id"], doc["id"])
            return f"doc{doc['owner_id']}_{doc['id']}"
        finally:
            if temp_created:
                self.gif.cleanup(actual_path)

    def _maybe_transform(self, path: str):
        """Pad/crop the gif into vk's limits; on failure post the original."""
        try:
            info = self.gif.info(path)
            if "error" in info or info.get("compliant"):
                return path, False
            log.info("gif %s is %.2f:1, transforming for vk",
                     os.path.basename(path), info["aspect_ratio"])
            return self.gif.transform(path), True
        except Exception as e:
            log.warning("gif transform failed (%s), using the original", e)
            return path, False

    # -- posting ----------------------------------------------------------

    def post(self, api, target_id: str, message: Optional[str],
             attachment: Optional[str], publish_ts: Optional[int],
             post_data: Optional[dict] = None) -> dict:
        if not message and not attachment:
            raise ValueError("nothing to post: need text or an attachment")

        params = {"owner_id": -self._group_id(target_id)}
        if publish_ts:
            params["publish_date"] = publish_ts
        if message:
            params["message"] = message
        if attachment:
            params["attachments"] = attachment
        # post_data: gif options etc., wall.post ignores it

        result = self._call(api.wall.post, **params)
        log.info("wall.post owner_id=%s publish_date=%s -> post_id=%s",
                 params["owner_id"], publish_ts or "now", result.get("post_id"))
        return result
