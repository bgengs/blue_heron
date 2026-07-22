# photo_catalog.json → Process titles (2026-07-22)

## Ask
Use Claude-authored `photo_catalog.json` to set titles/descriptions when processing photos.

## Done
- `server/photo_catalog.py` — indexes by basename + embedded `DJI_…` id so
  originals and `gbh_fly_*` / `exp/` copies share copy.
- `run_process` merges catalog into edits (overwrite titles/captions from
  catalog; keeps crop/rotate), persists to `data/edits.json`, passes title
  into framed banner generation.
- `edits.get_edit` fills empty title/caption from catalog for Editor display.
- Dashboard notes the catalog.

## Flow
Edit `photo_catalog.json` → Admin Process → titles on framed banners +
edits.json → Publish → `web/data/photos.json` captions.
