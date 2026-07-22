# Brand framing + heron badge protection (2026-07-22)

## Ask
Use brand assets (`heron_badge`, `herons_bg` / `herons_verified`, gallery logos) for
photo protection and a framed banner with Bernie logo + cursive title above
`www.BlueHeron.Gallery`. Prefer fully Python framing over static PNG overlay.

## Done
- **Protection:** `core/config.py` corner watermark → `assets/heron_badge.png`
  (black square punched transparent in `load_watermark`).
- **Framed banner:** new `core/frame.py` builds navy bar with:
  - Bernie mark cropped from `herons_bg.png`
  - Cursive title (Segoe Script / fallbacks) above `www.BlueHeron.Gallery`
  - `heron_badge.png` on the right
- **Pipeline:** Process writes `output/framed/`; Publish copies to
  `web/images/framed/`. Title comes from Editor (`edits.json`).
- Smoke sample: `output/_smoke_framed_raw.jpg`

## Flow
Editor title → Process → `output/framed/{file}.jpg` → Publish → `web/images/framed/`
