"""Non-destructive per-photo edits: title, caption, crop, rotate.

Edits are stored in data/edits.json keyed by the raw filename. Crop is stored
as fractions (0..1) of the EXIF-oriented image, so it survives re-processing
and never touches the original file. The pipeline applies these just before
protection.
"""

import json
import threading
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

from . import settings

_lock = threading.Lock()


def load_edits() -> dict:
    if not settings.EDITS_JSON.exists():
        return {}
    try:
        return json.loads(settings.EDITS_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def get_edit(filename: str) -> dict:
    return load_edits().get(filename, {})


def save_edit(filename: str, *, title: str = "", caption: str = "",
              crop: Optional[dict] = None, rotate: int = 0) -> dict:
    with _lock:
        edits = load_edits()
        entry = edits.get(filename, {})
        entry["title"] = title
        entry["caption"] = caption
        entry["rotate"] = int(rotate) % 360
        # crop = {x, y, w, h} as fractions, or None to clear
        if crop and all(k in crop for k in ("x", "y", "w", "h")):
            entry["crop"] = {k: max(0.0, min(1.0, float(crop[k]))) for k in ("x", "y", "w", "h")}
        else:
            entry.pop("crop", None)
        edits[filename] = entry
        settings.EDITS_JSON.parent.mkdir(parents=True, exist_ok=True)
        settings.EDITS_JSON.write_text(
            json.dumps(edits, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return entry


def slug_for(filename: str) -> str:
    return Path(filename).stem.lower().replace(" ", "-").replace("_", "-")


def apply_edits_to_image(src: Path, edit: dict) -> Optional[Image.Image]:
    """Return an oriented, rotated, cropped copy — or None if no geometry edit.

    Only geometry (rotate/crop) produces a new image. Title/caption are
    metadata and handled elsewhere.
    """
    crop = edit.get("crop")
    rotate = int(edit.get("rotate", 0)) % 360
    if not crop and not rotate:
        return None

    img = ImageOps.exif_transpose(Image.open(src))
    if img.mode != "RGB":
        img = img.convert("RGB")
    if rotate:
        # PIL rotates counter-clockwise; expand keeps the whole frame.
        img = img.rotate(-rotate, expand=True)
    if crop:
        w, h = img.size
        x0 = int(round(crop["x"] * w))
        y0 = int(round(crop["y"] * h))
        x1 = int(round((crop["x"] + crop["w"]) * w))
        y1 = int(round((crop["y"] + crop["h"]) * h))
        x0, x1 = sorted((max(0, x0), min(w, x1)))
        y0, y1 = sorted((max(0, y0), min(h, y1)))
        if x1 - x0 >= 8 and y1 - y0 >= 8:
            img = img.crop((x0, y0, x1, y1))
    return img
