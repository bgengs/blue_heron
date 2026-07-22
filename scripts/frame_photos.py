#!/usr/bin/env python3
"""Add decorative frames and artist banners to photos (pure Python / Pillow).

Wraps each photo in a matte/border and draws an optional banner that carries
artist metadata: name, artwork title, website, year, medium, price. Several
built-in themes give different looks, from a clean gallery placard to a
handwritten polaroid or a cinematic filmstrip.

The banner text is composed from whatever metadata you supply; empty fields
are skipped so there are no dangling separators.

Usage examples:
    # Preview every theme on one image (great first step):
    python frame_photos.py --preview resized/lg/heron-1.jpg \
        --name "Jane Rivers" --title "Great Blue Herons" --website "janerivers.art"

    # Frame a whole folder with one theme:
    python frame_photos.py --theme gallery --input resized/lg --output framed \
        --name "Jane Rivers" --website "janerivers.art" --year 2026

    # Per-image metadata via a JSON manifest (filename -> fields):
    python frame_photos.py --theme classic --manifest captions.json

    # List available themes:
    python frame_photos.py --list-themes
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont, ImageOps

# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]
Meta = dict[str, str]

SOURCE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}

# Logical font name -> Windows font filename. Resolved against the system font
# directory with graceful fallbacks (see load_font).
FONT_FILES: dict[str, str] = {
    "sans": "segoeui.ttf",
    "sans-bold": "segoeuib.ttf",
    "sans-light": "segoeuil.ttf",
    "sans-semilight": "segoeuisl.ttf",
    "sans-italic": "segoeuii.ttf",
    "serif": "georgia.ttf",
    "serif-bold": "georgiab.ttf",
    "serif-italic": "georgiai.ttf",
    "serif-bolditalic": "georgiaz.ttf",
    "elegant": "constan.ttf",
    "elegant-bold": "constanb.ttf",
    "elegant-italic": "constani.ttf",
    "mono": "consola.ttf",
    "mono-bold": "consolab.ttf",
    "script": "segoesc.ttf",
    "script-bold": "segoescb.ttf",
    "print": "segoepr.ttf",
    "impact": "impact.ttf",
}

# Cross-platform fallback filenames searched by name if the primary is missing.
_FALLBACK_FONTS = ["DejaVuSans.ttf", "DejaVuSerif.ttf", "Arial.ttf", "arial.ttf"]

_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


# --------------------------------------------------------------------------- #
# Theme model
# --------------------------------------------------------------------------- #


@dataclass
class Segment:
    """A run of text with its own font/size/color, laid out on a baseline."""

    text: str
    font: str = "sans"
    size: int = 34
    color: RGB = (20, 20, 20)
    tracking: float = 0.0  # extra px between characters (letter-spacing)


# A line is a horizontal sequence of segments; a block is a list of lines.
Line = list[Segment]
LinesBuilder = Callable[[Meta], list[Line]]


@dataclass
class Theme:
    display_name: str
    lines_builder: LinesBuilder
    # Matte / border widths in design px (top, right, bottom, left).
    matte: tuple[int, int, int, int] = (60, 60, 160, 60)
    matte_color: RGB = (255, 255, 255)
    # Thin accent keyline drawn around the photo.
    keyline_color: RGB | None = None
    keyline_width: int = 2
    keyline_inset: int = 0  # gap between photo edge and keyline (design px)
    # Banner placement: "below" (in bottom matte) or "overlay" (on the photo).
    banner_mode: str = "below"
    banner_height: int = 220  # design px, used for overlay mode
    banner_bg: RGBA | None = None  # overlay bar color; None = transparent
    banner_gradient: bool = False  # fade overlay from top->bottom
    align: str = "center"  # left | center | right
    pad_x: int = 40  # horizontal padding inside banner (design px)
    line_gap: int = 10  # vertical gap between text lines (design px)
    # Optional thin rule drawn just above the text block (e.g. gold accent).
    accent_color: RGB | None = None
    accent_width: int = 2
    accent_length: int = 90  # design px (0 = full content width)
    accent_gap: int = 24  # gap between rule and first text line
    special: str | None = None  # None | "film"
    background: RGB | None = None  # canvas background (defaults to matte_color)


# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #


def _windows_font_dir() -> Path:
    return Path(r"C:\Windows\Fonts")


def load_font(logical: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a font by logical name at ``size`` px, with caching and fallback."""
    size = max(1, int(size))
    key = (logical, size)
    if key in _font_cache:
        return _font_cache[key]

    filename = FONT_FILES.get(logical, FONT_FILES["sans"])
    candidates = [
        _windows_font_dir() / filename,
        Path(filename),  # let PIL search its own dirs / cwd
    ]
    candidates += [Path(f) for f in _FALLBACK_FONTS]

    font: ImageFont.FreeTypeFont | None = None
    for cand in candidates:
        try:
            font = ImageFont.truetype(str(cand), size)
            break
        except (OSError, ValueError):
            continue
    if font is None:
        # Absolute last resort: Pillow's built-in bitmap font, scaled.
        font = ImageFont.load_default(size)

    _font_cache[key] = font
    return font


# --------------------------------------------------------------------------- #
# Text layout helpers
# --------------------------------------------------------------------------- #


def _segment_width(seg: Segment, scale: float) -> float:
    font = load_font(seg.font, round(seg.size * scale))
    width = font.getlength(seg.text)
    if seg.tracking:
        width += seg.tracking * scale * max(0, len(seg.text) - 1)
    return width


def _line_metrics(line: Line, scale: float) -> tuple[float, int, int]:
    """Return (total_width, max_ascent, max_descent) for a line of segments."""
    total_w = 0.0
    max_asc = 0
    max_desc = 0
    for seg in line:
        font = load_font(seg.font, round(seg.size * scale))
        asc, desc = font.getmetrics()
        max_asc = max(max_asc, asc)
        max_desc = max(max_desc, desc)
        total_w += _segment_width(seg, scale)
    return total_w, max_asc, max_desc


def _draw_line(
    draw: ImageDraw.ImageDraw,
    line: Line,
    x: float,
    baseline: float,
    scale: float,
) -> None:
    """Draw a line of segments starting at ``x`` on the given baseline."""
    cursor = x
    for seg in line:
        font = load_font(seg.font, round(seg.size * scale))
        if seg.tracking:
            for ch in seg.text:
                draw.text((cursor, baseline), ch, font=font, fill=seg.color, anchor="ls")
                cursor += font.getlength(ch) + seg.tracking * scale
        else:
            draw.text((cursor, baseline), seg.text, font=font, fill=seg.color, anchor="ls")
            cursor += font.getlength(seg.text)


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    lines: list[Line],
    region: tuple[int, int, int, int],
    align: str,
    line_gap: int,
    scale: float,
    accent: tuple[RGB, int, int, int] | None,
) -> None:
    """Vertically center a block of lines inside ``region`` (l, t, r, b)."""
    if not lines:
        return
    rl, rt, rr, rb = region
    region_w = rr - rl
    region_h = rb - rt
    gap = round(line_gap * scale)

    metrics = [_line_metrics(ln, scale) for ln in lines]
    line_heights = [asc + desc for _, asc, desc in metrics]
    block_h = sum(line_heights) + gap * (len(lines) - 1)

    accent_h = 0
    if accent:
        _, a_w, _a_len, a_gap = accent
        accent_h = round(a_w * scale) + round(a_gap * scale)

    start_y = rt + max(0, (region_h - block_h - accent_h) // 2)

    if accent:
        a_color, a_w, a_len, a_gap = accent
        length = round((a_len if a_len else region_w) * scale)
        if align == "left":
            ax = rl
        elif align == "right":
            ax = rr - length
        else:
            ax = rl + (region_w - length) // 2
        ay = start_y
        draw.rectangle([ax, ay, ax + length, ay + round(a_w * scale)], fill=a_color)
        start_y += round(a_w * scale) + round(a_gap * scale)

    y = start_y
    for (total_w, asc, _desc), line, lh in zip(metrics, lines, line_heights):
        if align == "left":
            x = rl
        elif align == "right":
            x = rr - total_w
        else:
            x = rl + (region_w - total_w) / 2
        _draw_line(draw, line, x, y + asc, scale)
        y += lh + gap


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _scaled_matte(theme: Theme, scale: float) -> tuple[int, int, int, int]:
    return tuple(round(m * scale) for m in theme.matte)  # type: ignore[return-value]


def _draw_overlay_banner(
    photo: Image.Image, theme: Theme, meta: Meta, scale: float
) -> None:
    """Draw an overlay banner directly onto the photo (bottom-anchored)."""
    lines = [ln for ln in theme.lines_builder(meta) if ln]
    if not lines and not theme.banner_bg:
        return
    w, h = photo.size
    band_h = round(theme.banner_height * scale)
    band_top = h - band_h

    if theme.banner_bg is not None:
        overlay = Image.new("RGBA", (w, band_h), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        r, g, b, a = theme.banner_bg
        if theme.banner_gradient:
            for row in range(band_h):
                frac = row / max(1, band_h - 1)
                odraw.line([(0, row), (w, row)], fill=(r, g, b, int(a * frac)))
        else:
            odraw.rectangle([0, 0, w, band_h], fill=(r, g, b, a))
        photo.paste(overlay, (0, band_top), overlay)

    draw = ImageDraw.Draw(photo)
    pad = round(theme.pad_x * scale)
    region = (pad, band_top, w - pad, h - round(theme.pad_x * scale * 0.4))
    accent = (
        (theme.accent_color, theme.accent_width, theme.accent_length, theme.accent_gap)
        if theme.accent_color
        else None
    )
    _draw_text_block(draw, lines, region, theme.align, theme.line_gap, scale, accent)


def _draw_film_sprockets(
    canvas: Image.Image, matte: tuple[int, int, int, int], scale: float
) -> None:
    """Draw filmstrip sprocket holes along the top and bottom black bars."""
    top, right, bottom, left = matte
    w, h = canvas.size
    draw = ImageDraw.Draw(canvas)
    hole_w = round(26 * scale)
    hole_h = round(18 * scale)
    step = round(60 * scale)
    radius = round(4 * scale)
    top_y = (top - hole_h) // 2
    bot_y = (h - bottom) + round(8 * scale)
    x = step
    while x + hole_w < w - step:
        draw.rounded_rectangle(
            [x, top_y, x + hole_w, top_y + hole_h], radius=radius, fill=(230, 230, 230)
        )
        draw.rounded_rectangle(
            [x, bot_y, x + hole_w, bot_y + hole_h], radius=radius, fill=(230, 230, 230)
        )
        x += step


def render(image: Image.Image, theme: Theme, meta: Meta) -> Image.Image:
    """Return a new framed image for ``image`` using ``theme`` and ``meta``."""
    photo = image.convert("RGB").copy()
    w, h = photo.size
    scale = max(0.35, w / 1600.0)

    if theme.banner_mode == "overlay":
        _draw_overlay_banner(photo, theme, meta, scale)

    top, right, bottom, left = _scaled_matte(theme, scale)
    bg = theme.background or theme.matte_color
    canvas = Image.new("RGB", (w + left + right, h + top + bottom), bg)
    canvas.paste(photo, (left, top))

    draw = ImageDraw.Draw(canvas)

    # Accent keyline around the photo.
    if theme.keyline_color:
        inset = round(theme.keyline_inset * scale)
        kw = max(1, round(theme.keyline_width * scale))
        x0 = left - inset
        y0 = top - inset
        x1 = left + w + inset
        y1 = top + h + inset
        draw.rectangle([x0, y0, x1 - 1, y1 - 1], outline=theme.keyline_color, width=kw)

    if theme.special == "film":
        _draw_film_sprockets(canvas, (top, right, bottom, left), scale)

    # Banner text drawn in the bottom matte area.
    if theme.banner_mode == "below":
        lines = [ln for ln in theme.lines_builder(meta) if ln]
        pad = round(theme.pad_x * scale)
        region_top = top + h
        if theme.special == "film":
            # Reserve a band under the photo for the bottom sprocket row.
            region_top += round(34 * scale)
        region = (left + pad, region_top, left + w - pad, top + h + bottom)
        accent = (
            (theme.accent_color, theme.accent_width, theme.accent_length, theme.accent_gap)
            if theme.accent_color
            else None
        )
        _draw_text_block(draw, lines, region, theme.align, theme.line_gap, scale, accent)

    return canvas


# --------------------------------------------------------------------------- #
# Themes
# --------------------------------------------------------------------------- #


def _get(meta: Meta, key: str) -> str:
    return (meta.get(key) or "").strip()


def _lines_minimal(meta: Meta) -> list[Line]:
    ink = (25, 25, 25)
    grey = (120, 120, 120)
    line1: Line = []
    title = _get(meta, "title")
    name = _get(meta, "name")
    if title:
        line1.append(Segment(title, "sans-bold", 34, ink))
    if title and name:
        line1.append(Segment("   ", "sans", 34, grey))
    if name:
        line1.append(Segment(name, "sans", 34, grey))
    line2: Line = []
    site = _get(meta, "website")
    if site:
        line2.append(Segment(site.upper(), "sans-semilight", 24, grey, tracking=2))
    return [ln for ln in (line1, line2) if ln]


def _lines_gallery(meta: Meta) -> list[Line]:
    ink = (30, 30, 30)
    grey = (110, 110, 110)
    lines: list[Line] = []
    title = _get(meta, "title")
    if title:
        lines.append([Segment(title, "serif-italic", 40, ink)])
    name_bits: Line = []
    name = _get(meta, "name")
    year = _get(meta, "year")
    if name:
        name_bits.append(Segment(name, "serif", 30, ink))
    if name and year:
        name_bits.append(Segment(f", {year}", "serif", 30, grey))
    if name_bits:
        lines.append(name_bits)
    detail: Line = []
    medium = _get(meta, "medium")
    if medium:
        detail.append(Segment(medium, "serif-italic", 24, grey))
    if detail:
        lines.append(detail)
    foot: Line = []
    site = _get(meta, "website")
    price = _get(meta, "price")
    if site:
        foot.append(Segment(site, "serif", 24, grey))
    if site and price:
        foot.append(Segment("    ", "serif", 24, grey))
    if price:
        foot.append(Segment(price, "serif", 24, grey))
    if foot:
        lines.append(foot)
    return lines


def _lines_classic(meta: Meta) -> list[Line]:
    ink = (40, 32, 24)
    grey = (120, 100, 78)
    lines: list[Line] = []
    title = _get(meta, "title")
    if title:
        lines.append([Segment(title, "serif-bold", 40, ink)])
    name = _get(meta, "name")
    if name:
        lines.append([Segment(name, "serif-italic", 30, ink)])
    foot: Line = []
    site = _get(meta, "website")
    year = _get(meta, "year")
    if site:
        foot.append(Segment(site.upper(), "serif", 22, grey, tracking=2))
    if site and year:
        foot.append(Segment("  |  ", "serif", 22, grey))
    if year:
        foot.append(Segment(year, "serif", 22, grey, tracking=2))
    if foot:
        lines.append(foot)
    return lines


def _lines_dark(meta: Meta) -> list[Line]:
    white = (245, 245, 245)
    gold = (208, 176, 112)
    lines: list[Line] = []
    title = _get(meta, "title")
    if title:
        lines.append([Segment(title, "sans-bold", 40, white)])
    row: Line = []
    name = _get(meta, "name")
    site = _get(meta, "website")
    if name:
        row.append(Segment(name, "sans-light", 28, (215, 215, 215)))
    if name and site:
        row.append(Segment("   \u2022   ", "sans-light", 28, gold))
    if site:
        row.append(Segment(site, "sans-light", 28, gold))
    if row:
        lines.append(row)
    return lines


def _lines_film(meta: Meta) -> list[Line]:
    white = (235, 235, 235)
    grey = (150, 150, 150)
    lines: list[Line] = []
    title = _get(meta, "title")
    if title:
        lines.append([Segment(title.upper(), "mono-bold", 30, white, tracking=3)])
    row: Line = []
    name = _get(meta, "name")
    site = _get(meta, "website")
    if name:
        row.append(Segment(name, "mono", 22, grey))
    if name and site:
        row.append(Segment("   //   ", "mono", 22, grey))
    if site:
        row.append(Segment(site, "mono", 22, grey))
    if row:
        lines.append(row)
    return lines


def _lines_polaroid(meta: Meta) -> list[Line]:
    ink = (40, 40, 45)
    grey = (110, 110, 120)
    lines: list[Line] = []
    title = _get(meta, "title")
    if title:
        lines.append([Segment(title, "script", 56, ink)])
    row: Line = []
    name = _get(meta, "name")
    site = _get(meta, "website")
    if name:
        row.append(Segment(name, "print", 28, grey))
    if name and site:
        row.append(Segment("   ", "print", 28, grey))
    if site:
        row.append(Segment(site, "print", 28, grey))
    if row:
        lines.append(row)
    return lines


def _lines_elegant(meta: Meta) -> list[Line]:
    ink = (35, 35, 35)
    grey = (120, 120, 120)
    lines: list[Line] = []
    name = _get(meta, "name")
    if name:
        lines.append([Segment(name.upper(), "elegant", 32, ink, tracking=6)])
    title = _get(meta, "title")
    if title:
        lines.append([Segment(title, "elegant-italic", 28, grey)])
    site = _get(meta, "website")
    if site:
        lines.append([Segment(site, "elegant", 22, grey, tracking=2)])
    return lines


THEMES: dict[str, Theme] = {
    "minimal": Theme(
        display_name="Minimal",
        lines_builder=_lines_minimal,
        matte=(50, 50, 150, 50),
        matte_color=(255, 255, 255),
        keyline_color=(220, 220, 220),
        keyline_width=2,
        align="left",
        pad_x=8,
    ),
    "gallery": Theme(
        display_name="Gallery placard",
        lines_builder=_lines_gallery,
        matte=(70, 70, 260, 70),
        matte_color=(252, 251, 248),
        keyline_color=(200, 198, 192),
        keyline_width=1,
        keyline_inset=14,
        align="left",
        pad_x=6,
        line_gap=12,
    ),
    "classic": Theme(
        display_name="Classic cream",
        lines_builder=_lines_classic,
        matte=(90, 90, 240, 90),
        matte_color=(244, 238, 226),
        keyline_color=(170, 150, 120),
        keyline_width=2,
        keyline_inset=18,
        align="center",
        line_gap=14,
        accent_color=(170, 150, 120),
        accent_width=2,
        accent_length=120,
        accent_gap=22,
    ),
    "dark": Theme(
        display_name="Dark overlay",
        lines_builder=_lines_dark,
        matte=(0, 0, 0, 0),
        matte_color=(15, 15, 15),
        banner_mode="overlay",
        banner_height=260,
        banner_bg=(0, 0, 0, 210),
        banner_gradient=True,
        align="center",
        line_gap=12,
        accent_color=(208, 176, 112),
        accent_width=2,
        accent_length=90,
        accent_gap=20,
    ),
    "film": Theme(
        display_name="Filmstrip",
        lines_builder=_lines_film,
        matte=(90, 30, 150, 30),
        matte_color=(12, 12, 12),
        align="center",
        line_gap=12,
        special="film",
    ),
    "polaroid": Theme(
        display_name="Polaroid",
        lines_builder=_lines_polaroid,
        matte=(60, 60, 300, 60),
        matte_color=(253, 252, 247),
        align="center",
        line_gap=6,
    ),
    "elegant": Theme(
        display_name="Elegant serif",
        lines_builder=_lines_elegant,
        matte=(70, 70, 230, 70),
        matte_color=(250, 250, 250),
        keyline_color=(30, 30, 30),
        keyline_width=1,
        keyline_inset=16,
        align="center",
        line_gap=14,
        accent_color=(180, 150, 90),
        accent_width=1,
        accent_length=70,
        accent_gap=20,
    ),
}


# --------------------------------------------------------------------------- #
# Preview sheet
# --------------------------------------------------------------------------- #


def make_preview(image: Image.Image, meta: Meta, columns: int = 2) -> Image.Image:
    """Render every theme on ``image`` and tile the results into one sheet."""
    # Work from a downscaled copy so the preview renders quickly.
    preview_src = image.copy()
    preview_src.thumbnail((900, 900), Image.Resampling.LANCZOS)

    tiles: list[tuple[str, Image.Image]] = []
    for key, theme in THEMES.items():
        tiles.append((key, render(preview_src, theme, meta)))

    label_h = 40
    pad = 24
    cell_w = max(t.width for _, t in tiles)
    cell_h = max(t.height for _, t in tiles) + label_h
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new(
        "RGB",
        (columns * cell_w + pad * (columns + 1), rows * cell_h + pad * (rows + 1)),
        (60, 60, 63),
    )
    draw = ImageDraw.Draw(sheet)
    label_font = load_font("sans-bold", 26)

    for idx, (key, tile) in enumerate(tiles):
        r, c = divmod(idx, columns)
        x = pad + c * (cell_w + pad)
        y = pad + r * (cell_h + pad)
        draw.text((x, y), f"{key}", font=label_font, fill=(240, 240, 240))
        sheet.paste(tile, (x, y + label_h))
    return sheet


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def collect_sources(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        p for p in path.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_EXTENSIONS
    )


def load_manifest(manifest_path: Path) -> dict[str, Meta]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Manifest must be a JSON object mapping filename -> fields.")
    return {str(k): dict(v) for k, v in data.items()}


def meta_from_args(args: argparse.Namespace) -> Meta:
    return {
        "name": args.name or "",
        "title": args.title or "",
        "website": args.website or "",
        "year": args.year or "",
        "medium": args.medium or "",
        "price": args.price or "",
    }


def save_jpeg(img: Image.Image, dest: Path, quality: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="JPEG", quality=quality, optimize=True, progressive=True)


def build_parser() -> argparse.ArgumentParser:
    script_dir = Path(__file__).resolve().parent
    root = script_dir.parent
    parser = argparse.ArgumentParser(
        description="Add frames + artist banners to photos.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", type=Path, default=root / "resized" / "lg",
                        help="Image file or directory to frame.")
    parser.add_argument("--output", type=Path, default=root / "framed",
                        help="Output directory.")
    parser.add_argument("--theme", default="gallery",
                        help="Theme name, or 'all' to render every theme.")
    parser.add_argument("--preview", type=Path, default=None, metavar="IMAGE",
                        help="Render a single sheet of all themes for one image.")
    parser.add_argument("--list-themes", action="store_true",
                        help="List available themes and exit.")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="JSON file mapping filename -> metadata fields.")
    parser.add_argument("--quality", type=int, default=90, help="JPEG quality (1-100).")
    # Metadata (applied to all images unless a manifest overrides).
    parser.add_argument("--name", default="", help="Artist name.")
    parser.add_argument("--title", default="", help="Artwork title.")
    parser.add_argument("--website", default="", help="Website / handle.")
    parser.add_argument("--year", default="", help="Year.")
    parser.add_argument("--medium", default="", help="Medium (e.g. 'Archival pigment print').")
    parser.add_argument("--price", default="", help="Price (e.g. '$450').")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_themes:
        print("Available themes:")
        for key, theme in THEMES.items():
            print(f"  {key:<10} {theme.display_name}")
        return 0

    base_meta = meta_from_args(args)
    manifest = load_manifest(args.manifest) if args.manifest else {}

    # Preview mode: one sheet of all themes for a single image.
    if args.preview is not None:
        if not args.preview.is_file():
            print(f"Preview image not found: {args.preview}", file=sys.stderr)
            return 1
        with Image.open(args.preview) as im:
            image = ImageOps.exif_transpose(im)
            meta = {**base_meta, **manifest.get(args.preview.name, {})}
            sheet = make_preview(image, meta)
        args.output.mkdir(parents=True, exist_ok=True)
        dest = args.output / f"_preview_{args.preview.stem}.jpg"
        save_jpeg(sheet, dest, args.quality)
        print(f"Wrote theme preview -> {dest}")
        return 0

    if args.theme != "all" and args.theme not in THEMES:
        print(f"Unknown theme '{args.theme}'. Use --list-themes.", file=sys.stderr)
        return 2
    theme_keys = list(THEMES) if args.theme == "all" else [args.theme]

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1
    sources = collect_sources(args.input)
    if not sources:
        print(f"No images found in {args.input}", file=sys.stderr)
        return 1

    print(f"Framing {len(sources)} image(s) with theme(s): {', '.join(theme_keys)}")
    written = 0
    for src in sources:
        meta = {**base_meta, **manifest.get(src.name, {})}
        try:
            with Image.open(src) as im:
                image = ImageOps.exif_transpose(im)
                for key in theme_keys:
                    framed = render(image, THEMES[key], meta)
                    if len(theme_keys) > 1:
                        dest = args.output / key / src.name
                    else:
                        dest = args.output / src.name
                    save_jpeg(framed, dest.with_suffix(".jpg"), args.quality)
                    print(f"  {key:<10} -> {dest.with_suffix('.jpg')}")
                    written += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR on {src.name}: {exc}", file=sys.stderr)

    print(f"\nDone. Wrote {written} framed image(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
