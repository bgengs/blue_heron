# Photo editor / admin photos exploration (2026-07-22)

Mapped how editor listing/counter, thumbs, Live/active, and raw scanning work.

## Ordering
- Editor: `server/main.py` `_raw_photo_paths()` — `raw/**/*.jpg` sorted by **basename** only → `1/N` in `_editor_neighbors`.
- Lexical: `DJI_*` before `gbh_fly_*`, so Photoshop set is buried in a large total.
- Public gallery / Photos admin: `sort` on manifest (`web/data/photos.json`); API sorts by `sort`.

## Flags
- Manifest `active` (= Live UI): public only; does **not** affect editor.
- No archive/skip/hide for editor today. Edits: title/caption/crop/rotate only.

## Thumbs
- Admin: `.thumb` 84×56 in `base.html`.
- Editor grid: `minmax(220px)`, `/admin/raw/?max=360`.
- Pipeline: `THUMBNAIL_MAX_PX = 300`.

## Change points
- (a) Archive out of editor: filter in `_raw_photo_paths` (+ edits flag or move files).
- (b) Larger thumbs: CSS + optional `?max=` / grid minmax.
- (c) gbh_fly as 1..N: filter/sort key in `_raw_photo_paths`, or renumber manifest `sort` for gallery.
