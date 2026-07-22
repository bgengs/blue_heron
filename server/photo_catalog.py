"""Load titles/descriptions from photo_catalog.json (Claude-authored).

Keyed by basename and by embedded DJI id so
  raw/DJI_….JPG
  raw/gbh_fly_0000_DJI_….jpg
  raw/exp/gbh_fly_0000_DJI_….jpg
all resolve to the same copy.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from . import settings

# gbh_fly_0012_DJI_20260721222309_0505_D.jpg → DJI_20260721222309_0505_D
_DJI_IN_NAME = re.compile(r"(DJI_\d+[A-Za-z0-9_]*)", re.IGNORECASE)


@lru_cache(maxsize=1)
def _catalog_path() -> Path:
    return settings.APP_ROOT / "photo_catalog.json"


@lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    """Map normalized keys → {title, description, file}."""
    path = _catalog_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    index: dict[str, dict] = {}
    for entry in data.get("photos") or []:
        title = (entry.get("title") or "").strip()
        desc = (entry.get("description") or entry.get("caption") or "").strip()
        if not title and not desc:
            continue
        payload = {"title": title, "description": desc, "file": entry.get("file", "")}
        file_path = str(entry.get("file") or "")
        name = Path(file_path).name
        if not name:
            continue
        for key in _keys_for(name):
            index[key] = payload
    return index


def _keys_for(name: str) -> list[str]:
    """All lookup keys for a filename."""
    keys = [name.lower(), Path(name).stem.lower()]
    m = _DJI_IN_NAME.search(name)
    if m:
        dji = m.group(1)
        keys.append(dji.lower())
        keys.append(Path(dji).stem.lower() if "." in dji else dji.lower())
        # stem without extension if DJI_…_D.JPG style
        if dji.lower().endswith(".jpg") or dji.lower().endswith(".jpeg"):
            keys.append(Path(dji).stem.lower())
    # dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def lookup(filename: str) -> Optional[dict]:
    """Return {title, description} for a raw filename, or None."""
    index = _index()
    if not index:
        return None
    name = Path(filename).name
    for key in _keys_for(name):
        hit = index.get(key)
        if hit:
            return hit
    return None


def apply_to_edit(filename: str, edit: dict, *, overwrite: bool = False) -> dict:
    """Merge catalog title/description into an edits entry.

    By default fills empty fields only. overwrite=True replaces title/caption
    from the catalog (used at Process time so the catalog stays authoritative).
    """
    hit = lookup(filename)
    if not hit:
        return edit
    out = dict(edit)
    title = hit.get("title") or ""
    desc = hit.get("description") or ""
    if overwrite or not (out.get("title") or "").strip():
        if title:
            out["title"] = title
    if overwrite or not (out.get("caption") or "").strip():
        if desc:
            out["caption"] = desc
    return out


def catalog_stats() -> dict:
    idx = _index()
    return {
        "path": str(_catalog_path()),
        "exists": _catalog_path().is_file(),
        "entries": len(idx),
    }


def clear_cache() -> None:
    _index.cache_clear()
    _catalog_path.cache_clear()
