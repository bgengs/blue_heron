"""Framed banner compositor — photo + Bernie logo + cursive title + heron badge.

Builds the site display / share frame in pure Pillow using brand assets:
  - assets/herons_bg.png   (Bernie Gengel mark cropped from the left banner)
  - assets/heron_badge.png (circular seal on the right)
  - cursive title above www.BlueHeron.Gallery in the center

The full-bleed templates herons_bg / herons_verified are the design reference;
we redraw the banner so the title can change per photo.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from core.config import (
    BANNER_NAVY,
    BANNER_WEBSITE,
    FRAME_BADGE_PATH,
    FRAME_TEMPLATE_PATH,
    FRAMED_MAX_PX,
)

# Banner height as a fraction of the photo width (matches ~762/8064 template).
_BANNER_RATIO = 0.11
_BANNER_MIN_H = 128

_SCRIPT_FONT_CANDIDATES = [
    "segoesc.ttf",       # Segoe Script
    "segoescb.ttf",
    "ITCEDSCR.TTF",      # Edwardian Script (common on Windows)
    "FREESCPT.TTF",      # Freestyle Script
    "BrushScript.ttf",
    "georgiai.ttf",      # fallback italic serif
    "timesi.ttf",
]


def _assets_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _font_dirs() -> list[Path]:
    windir = Path(__import__("os").environ.get("WINDIR", r"C:\Windows"))
    return [
        windir / "Fonts",
        Path("/usr/share/fonts"),
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
    ]


@lru_cache(maxsize=32)
def _load_font(size: int, script: bool = False) -> ImageFont.ImageFont:
    if script:
        names = _SCRIPT_FONT_CANDIDATES
    else:
        names = ["georgia.ttf", "georgiab.ttf", "times.ttf", "DejaVuSerif.ttf", "arial.ttf"]
    for d in _font_dirs():
        for name in names:
            path = d / name
            if path.is_file():
                try:
                    return ImageFont.truetype(str(path), size)
                except OSError:
                    continue
    return ImageFont.load_default()


@lru_cache(maxsize=1)
def _bernie_logo() -> Image.Image:
    """Crop the Bernie Gengel mark from the left side of the banner template."""
    root = _assets_root()
    template = Image.open(root / FRAME_TEMPLATE_PATH).convert("RGBA")
    w, h = template.size
    banner_top = int(h * 0.832)  # ~3774/4536
    # Design-space crop from earlier analysis (scaled to this template).
    left, top, right, bottom = 100, banner_top + 160, 960, h - 40
    crop = template.crop((left, top, right, bottom))
    return _punch_near_navy(crop)


@lru_cache(maxsize=1)
def _badge() -> Image.Image:
    root = _assets_root()
    badge = Image.open(root / FRAME_BADGE_PATH).convert("RGBA")
    return _punch_near_black(badge)


def _punch_near_black(im: Image.Image, threshold: int = 28) -> Image.Image:
    """Make near-black background transparent (badge sits on black square)."""
    arr = np.array(im)
    near = (arr[:, :, 0] < threshold) & (arr[:, :, 1] < threshold) & (arr[:, :, 2] < threshold) & (arr[:, :, 3] > 0)
    arr[near, 3] = 0
    return Image.fromarray(arr, "RGBA")


def _punch_near_navy(im: Image.Image) -> Image.Image:
    """Knock out the navy banner behind the Bernie logo crop."""
    arr = np.array(im)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    navy = (a > 0) & (r < 40) & (g < 55) & (b < 90) & (b >= g) & (b >= r)
    arr[navy, 3] = 0
    return Image.fromarray(arr, "RGBA")


def _with_opacity(im: Image.Image, opacity: float) -> Image.Image:
    """Scale alpha channel (opacity 0–1)."""
    arr = np.array(im)
    arr[:, :, 3] = (arr[:, :, 3].astype(np.float32) * opacity).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")

def render_framed(
    photo: Image.Image,
    title: str = "",
    website: str = BANNER_WEBSITE,
    max_px: int = FRAMED_MAX_PX,
) -> Image.Image:
    """Compose photo + navy brand banner with cursive title.

    Layout (top → bottom):
      [ photo, width-fitted ]
      [ Bernie logo | cursive title / website | heron badge ]
    """
    if photo.mode != "RGB":
        photo = photo.convert("RGB")

    # Fit photo to max dimension for site/framed use.
    pw, ph = photo.size
    longest = max(pw, ph)
    if longest > max_px:
        scale = max_px / longest
        photo = photo.resize((int(pw * scale), int(ph * scale)), Image.LANCZOS)
        pw, ph = photo.size

    banner_h = max(_BANNER_MIN_H, int(pw * _BANNER_RATIO))
    canvas = Image.new("RGB", (pw, ph + banner_h), BANNER_NAVY)
    canvas.paste(photo, (0, 0))

    banner = Image.new("RGBA", (pw, banner_h), (*BANNER_NAVY, 255))
    draw = ImageDraw.Draw(banner)

    # Side marks — height ~70% of banner.
    mark_h = int(banner_h * 0.72)
    pad = int(banner_h * 0.12)

    logo = _bernie_logo().copy()
    logo.thumbnail((int(mark_h * 1.35), mark_h), Image.LANCZOS)
    badge = _badge().copy()
    badge.thumbnail((mark_h, mark_h), Image.LANCZOS)
    logo = _with_opacity(logo, 0.90)
    badge = _with_opacity(badge, 0.90)

    logo_y = (banner_h - logo.height) // 2
    badge_y = (banner_h - badge.height) // 2
    banner.alpha_composite(logo, (pad, logo_y))
    banner.alpha_composite(badge, (pw - badge.width - pad, badge_y))

    # Text column between the marks.
    left_bound = pad + logo.width + pad
    right_bound = pw - pad - badge.width - pad
    text_w = max(40, right_bound - left_bound)
    cx = left_bound + text_w // 2

    title = (title or "").strip()
    website = (website or BANNER_WEBSITE).strip()

    # Size fonts relative to banner height.
    title_size = max(18, int(banner_h * 0.28))
    site_size = max(12, int(banner_h * 0.16))
    title_font = _load_font(title_size, script=True)
    site_font = _load_font(site_size, script=False)

    def _text_size(text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Shrink title to fit the text column.
    while title and title_size > 14:
        tw, _ = _text_size(title, title_font)
        if tw <= text_w * 0.95:
            break
        title_size -= 2
        title_font = _load_font(title_size, script=True)

    if title:
        tw, th = _text_size(title, title_font)
        sw, sh = _text_size(website, site_font)
        gap = max(22, int(banner_h * 0.22))  # clear air between title and URL
        block_h = th + gap + sh
        ty = (banner_h - block_h) // 2
        draw.text((cx - tw // 2, ty), title, font=title_font, fill=(244, 241, 233, 230))
        draw.text(
            (cx - sw // 2, ty + th + gap),
            website,
            font=site_font,
            fill=(220, 228, 235, 230),
        )
    else:
        sw, sh = _text_size(website, site_font)
        draw.text(
            (cx - sw // 2, (banner_h - sh) // 2),
            website,
            font=site_font,
            fill=(244, 241, 233, 255),
        )

    canvas.paste(banner.convert("RGB"), (0, ph))
    return canvas


def render_framed_to_path(
    photo: Image.Image,
    dest: Path,
    title: str = "",
    website: str = BANNER_WEBSITE,
    quality: int = 88,
) -> Path:
    framed = render_framed(photo, title=title, website=website)
    dest.parent.mkdir(parents=True, exist_ok=True)
    framed.save(dest, "JPEG", quality=quality, optimize=True)
    return dest
