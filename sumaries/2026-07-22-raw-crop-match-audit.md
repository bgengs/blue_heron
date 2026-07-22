# Raw crop match audit

Mapped `raw/` JPGs by embedded `DJI_…` id (script: `scripts/map_raw_crops.py`).

## Result

- **225** files, **75** unique DJI ids, **2** names with no DJI id.
- **74** ids appear **3×**: `DJI_*` at `raw/` + `gbh_fly_*` at `raw/` + same crop under `raw/exp/`.
- **1** id appears **1× only** (no crop): `DJI_20260721221326_0408_D.JPG`.
- **Orphan crop** (no DJI in filename): `gbh_fly_0074_Layer 1.jpg` (+ `exp/` copy). Same pixel size as 0408 (8064×4536); catalog titles differ (`Two at Home…` vs `Within Sight of the Barn`).
- `gbh_fly_0000`…`0074` indices: **no gaps**.

## Takeaway

The crop set is complete by index; the naming mismatch is **0408 ↔ Layer 1**. Likely fix: rename `gbh_fly_0074_Layer 1.jpg` to include `DJI_20260721221326_0408` if it is that crop, or export a real crop for 0408.
