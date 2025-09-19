"""VK posting backend: wall photo uploads, gifs as documents, wall.post."""

import logging
import os
from typing import Optional

import requests
import vk_api

log = logging.getLogger(__name__)


class VKClient:
    def __init__(self):
        pass

    def api_for(self, token: str):
        """Authenticated api object per token, cached."""
        return vk_api.VkApi(token=token).get_api()

    # -- uploading --------------------------------------------------------

    def upload_photo(self, api, path: str, group_id: int) -> str:
        server = api.photos.getWallUploadServer(group_id=group_id)
        with open(path, "rb") as fh:
            resp = requests.post(server["upload_url"], files={"photo": fh})
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
                   title: Optional[str] = None) -> str:
        """GIFs go up as documents."""
        server = api.docs.getWallUploadServer(group_id=group_id)
        with open(path, "rb") as fh:
            resp = requests.post(server["upload_url"], files={"file": fh})
        resp.raise_for_status()
        doc_data = resp.json()

        saved = api.docs.save(file=doc_data["file"],
                              title=title or os.path.basename(path),
                              group_id=group_id)
        doc = saved["doc"]
        log.info("uploaded gif %s as doc%d_%d",
                 os.path.basename(path), doc["owner_id"], doc["id"])
        return f"doc{doc['owner_id']}_{doc['id']}"

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
