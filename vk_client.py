"""VK posting backend: wall photo uploads, gifs as documents, wall.post."""

import logging
import os
from typing import Dict, Optional

import requests
import vk_api

from gif_transformer import GIFTransformer

log = logging.getLogger(__name__)

UPLOAD_TIMEOUT = (10, 300)  # (connect, read); big gifs read slowly, be generous


class VKClient:
    def __init__(self):
        self.gif = GIFTransformer()
        self._sessions: Dict[str, object] = {}

    def api_for(self, token: str):
        """Authenticated api object per token, cached."""
        if token not in self._sessions:
            session = vk_api.VkApi(token=token)
            self._sessions[token] = session.get_api()
        return self._sessions[token]

    # -- uploading --------------------------------------------------------

    def upload_photo(self, api, path: str, group_id: int) -> str:
        server = api.photos.getWallUploadServer(group_id=group_id)
        with open(path, "rb") as fh:
            resp = requests.post(server["upload_url"], files={"photo": fh}, timeout=UPLOAD_TIMEOUT)
        resp.raise_for_status()
        photo = resp.json()

        saved = api.photos.saveWallPhoto(
            server=photo["server"],
            photo=photo["photo"],
            hash=photo["hash"],
            group_id=group_id,
        )[0]
        log.info("uploaded photo %s as photo%d_%d",
                 os.path.basename(path), saved["owner_id"], saved["id"])
        return f"photo{saved['owner_id']}_{saved['id']}"

    def upload_gif(self, api, path: str, group_id: int,
                   title: Optional[str] = None, transform: bool = True) -> str:
        """GIFs go up as documents."""
        actual_path = path
        temp_created = False
        if transform:
            actual_path, temp_created = self._maybe_transform(path)

        try:
            # no group_id on purpose, see the VK docs for docs.getWallUploadServer
            server = api.docs.getWallUploadServer()
            with open(actual_path, "rb") as fh:
                resp = requests.post(server["upload_url"], files={"file": fh}, timeout=UPLOAD_TIMEOUT)
            resp.raise_for_status()
            doc_data = resp.json()

            saved = api.docs.save(file=doc_data["file"], title=title or os.path.basename(path))
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
            if "error" in info or info.get("vk_compliant"):
                return path, False
            log.info("gif %s is %.2f:1, transforming for vk",
                     os.path.basename(path), info["aspect_ratio"])
            return self.gif.transform(path), True
        except Exception as e:
            log.warning("gif transform failed (%s), using the original", e)
            return path, False

    # -- posting ----------------------------------------------------------

    def post_to_wall(self, api, owner_id: int, message: Optional[str],
                     attachment: Optional[str], publish_ts: Optional[int]) -> dict:
        if not message and not attachment:
            raise ValueError("nothing to post: need text or an attachment")

        params = {"owner_id": owner_id}
        if publish_ts:
            params["publish_date"] = publish_ts
        if message:
            params["message"] = message
        if attachment:
            params["attachments"] = attachment

        result = api.wall.post(**params)
        log.info("wall.post owner_id=%s publish_date=%s -> post_id=%s",
                 owner_id, publish_ts or "now", result.get("post_id"))
        return result
