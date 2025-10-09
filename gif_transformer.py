"""Fix gif aspect rattios: pad or center-crop frames into limits."""

import logging
import math
import os
import tempfile
from typing import Tuple

from PIL import Image, ImageSequence

log = logging.getLogger(__name__)


class GIFTransformer:
    def __init__(self):
        self.min_ratio = 0.66
        self.max_ratio = 2.5

    def compliant(self, width: int, height: int) -> bool:
        if not height:
            return False
        return self.min_ratio <= width / height <= self.max_ratio

    def target_size(self, width: int, height: int) -> Tuple[int, int]:
        """Dimensions to pad/crop to."""
        if self.compliant(width, height):
            return width, height

        if width / height < self.min_ratio:
            # too tall: widen, crop the height if that gets absurd
            new_w = math.ceil(height * self.min_ratio)
            new_h = height
        else:
            new_w = width
            new_h = math.ceil(width / self.max_ratio)

        # cap growth at 1.5x so file doesnt balloon
        if new_w > width * 1.5:
            new_w = math.ceil(width * 1.5)
            new_h = math.ceil(new_w / self.min_ratio)
        elif new_h > height * 1.5:
            new_h = math.ceil(height * 1.5)
            new_w = math.ceil(new_h * self.max_ratio)

        # ceil above can still land a hair outside the limits
        while not self.compliant(new_w, new_h):
            if new_w / new_h < self.min_ratio:
                new_w += 1
            else:
                new_h += 1
        return new_w, new_h

    def transform(self, path: str) -> str:
        """Return the path of a compliant temp copy."""
        with Image.open(path) as img:
            if img.format != "GIF":
                raise ValueError(f"{path} is not a gif")

            width, height = img.size
            if self.compliant(width, height):
                return path

            tw, th = self.target_size(width, height)
            log.info("transforming %s: %dx%d -> %dx%d",
                     os.path.basename(path), width, height, tw, th)

            tmp_dir = tempfile.mkdtemp()
            base = os.path.splitext(os.path.basename(path))[0]
            out_path = os.path.join(tmp_dir, f"{base}_vk.gif")

            frames = []
            durations = []
            for frame in ImageSequence.Iterator(img):
                try:
                    frames.append(self._fit_frame(frame, tw, th))
                    durations.append(frame.info.get("duration", 100))
                except Exception as e:
                    # one broken frame should not kill the whole gif
                    log.warning("skipping a frame: %s", e)

            if not frames:
                raise RuntimeError("no frames could be processed")

            while len(durations) < len(frames):
                durations.append(100)

            save_kw = {
                "format": "GIF",
                "save_all": True,
                "append_images": frames[1:],
                "duration": durations,
                "loop": img.info.get("loop", 0),
                "disposal": img.info.get("disposal", 2),
            }
            if "transparency" in img.info:
                save_kw["transparency"] = img.info["transparency"]

            try:
                frames[0].save(out_path, **save_kw)
            except Exception:
                log.warning("full-fidelity save failed, retrying plain", exc_info=True)
                frames[0].save(out_path, format="GIF", save_all=True,
                               append_images=frames[1:], duration=durations,
                               loop=img.info.get("loop", 0))
            return out_path

    def _fit_frame(self, frame: Image.Image, tw: int, th: int) -> Image.Image:
        """Crop then pad a frame onto the target canvas."""
        w, h = frame.size
        if w > tw:
            off = (w - tw) // 2
            frame = frame.crop((off, 0, off + tw, h))
            w = tw
        if h > th:
            off = (h - th) // 2
            frame = frame.crop((0, off, w, off + th))
            h = th

        if (w, h) == (tw, th):
            return frame

        canvas = Image.new(frame.mode, (tw, th), 0)
        if frame.mode == "P":
            palette = frame.getpalette()
            if palette:
                canvas.putpalette(palette)
        canvas.paste(frame, ((tw - w) // 2, (th - h) // 2))
        return canvas

    def info(self, path: str) -> dict:
        try:
            with Image.open(path) as img:
                if img.format != "GIF":
                    return {"error": "not a gif"}
                w, h = img.size
                return {
                    "width": w,
                    "height": h,
                    "aspect_ratio": round(w / h, 2),
                    "vk_compliant": self.compliant(w, h),
                    "frames": getattr(img, "n_frames", 1),
                }
        except Exception as e:
            return {"error": str(e)}

    def cleanup(self, path: str) -> None:
        try:
            real = os.path.realpath(path)
            base = os.path.realpath(tempfile.gettempdir())
            parent = os.path.dirname(real)
            if parent != base and not parent.startswith(base + os.sep):
                log.debug("refusing to clean %s: outside the temp dir", path)
                return
            if os.path.exists(real):
                os.remove(real)
                if parent != base:  # the mkdtemp() dir transform() made
                    try:
                        os.rmdir(parent)
                    except OSError:
                        pass
        except OSError as e:
            log.warning("could not remove temp gif %s: %s", path, e)
