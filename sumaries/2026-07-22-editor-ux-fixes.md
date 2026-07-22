# Editor UX fixes (2026-07-22)

## Problem
Editor crop overlay used `box-shadow: 0 0 0 9999px` without clipping, which painted over the title/caption form so fields felt unusable. Crop felt mandatory; no Save & next.

## Fixes
- Clip crop shade with `overflow:hidden` on `.stage`; raise form `z-index`
- Crop optional: start full-frame; **No crop (full frame)** button
- **Save & next →**, Prev/Next links, photo index
- Restart `python -m server.main` required (no auto-reload)
