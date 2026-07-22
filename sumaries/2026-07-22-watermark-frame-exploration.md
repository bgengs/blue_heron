# Watermark / framed-banner exploration (2026-07-22)

Mapped photo protection and framing across `core/`, `server/`, and `scripts/`.

## Protection pipeline
- Entry: `server/pipeline.py` → `run_process()` → `core.processor.process_single_image()`
- Visible marks: `core/watermark.py` (`apply_visible_watermark`, `apply_full_frame_overlay`)
- Invisible: `core/protection.py` (`apply_web_protection`, DCT + micro-mark + hashes)
- Asset paths: `core/config.py` (`WATERMARK_ASSETS`, `BASE_BG_ASSETS`)
- Variants: `output/{thumbnails,web,print,watermarked}`; publish copies web/thumb/print only

## Framing
- Standalone: `scripts/frame_photos.py` (`render()`, themes in `THEMES`)
- Not wired into Process/Publish; no `framed`/`banner`/`verified` output variant yet
- New assets (`herons_verified.png`, logos, badge) exist under `assets/` but are unreferenced

## Integration note
Point `WATERMARK_ASSETS` at `assets/herons_verified.png` (or a downsized badge) for protection; use `frame_photos.py` gallery theme with title + `www.blueheron.gallery` for banners, optionally as a new pipeline variant later.
