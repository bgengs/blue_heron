# Photo tools

Two pure-Python (Pillow) scripts:

- [`resize_photos.py`](#photo-resizing) — responsive size variants.
- [`frame_photos.py`](#photo-frames--artist-banners) — decorative frames + artist banners.

# Photo resizing

`resize_photos.py` downscales the high-resolution originals in `source_photos/`
into responsive size variants (`xs`, `sm`, `md`, `lg`, `xl`) while keeping the
aspect ratio and image quality high.

## Setup

```bash
pip install -r scripts/requirements.txt
```

## Usage

Run with defaults (reads `source_photos/`, writes `resized/`):

```bash
python scripts/resize_photos.py
```

Output layout (default `--group-by size`):

```
resized/
  xs/  heron-1.jpg   (480px wide)
  sm/  heron-1.jpg   (768px wide)
  md/  heron-1.jpg   (1280px wide)
  lg/  heron-1.jpg   (1920px wide)
  xl/  heron-1.jpg   (2560px wide)
```

## Common options

| Option            | Default             | Description                                              |
| ----------------- | ------------------- | -------------------------------------------------------- |
| `--input`         | `../source_photos`  | Source image directory.                                  |
| `--output`        | `../resized`        | Where variants are written.                              |
| `--sizes`         | see below           | Space-separated `name=width` pairs.                      |
| `--formats`       | `jpeg`              | One or more of `jpeg`, `webp`, `png`.                    |
| `--quality`       | `85`                | Lossy quality (1-100). 82-88 keeps quality high.         |
| `--group-by`      | `size`              | `size` -> `output/md/photo.jpg`; `name` -> `output/photo/photo-md.jpg`. |
| `--allow-upscale` | off                 | Allow enlarging beyond the source width.                 |
| `--overwrite`     | off                 | Overwrite existing files instead of skipping.            |

Default sizes (width in px): `xs=480 sm=768 md=1280 lg=1920 xl=2560`.

## Examples

Custom sizes and higher quality:

```bash
python scripts/resize_photos.py --sizes xs=320 sm=640 md=1024 lg=1600 xl=2048 --quality 88
```

Generate both JPEG and WebP (WebP is smaller at the same quality):

```bash
python scripts/resize_photos.py --formats jpeg webp
```

## Quality notes

- Uses **Lanczos** resampling (best quality for downscaling).
- JPEGs are saved **progressive** + **optimized**, quality 85 by default.
- The embedded **ICC color profile** and **EXIF orientation** are preserved.
- Images are never upscaled by default, so no quality is invented.

---

# Photo frames + artist banners

`frame_photos.py` wraps a photo in a matte/border and draws an optional banner
carrying artist metadata: **name, artwork title, website, year, medium, price**.
Empty fields are skipped automatically, so you only fill in what you need.

## Themes

| Theme      | Look                                                            |
| ---------- | -------------------------------------------------------------- |
| `minimal`  | Thin keyline, slim left-aligned caption bar (sans).            |
| `gallery`  | Museum placard: italic title, artist, medium/year, website.   |
| `classic`  | Cream matte, centered serif caption with a gold rule.          |
| `dark`     | Gradient overlay banner on the photo, gold accent (no border). |
| `film`     | Black filmstrip with sprocket holes, monospaced caption.       |
| `polaroid` | Thick white border with a handwritten (script) caption.        |
| `elegant`  | Letter-spaced serif name, italic title, gold rule.             |

List them anytime:

```bash
python scripts/frame_photos.py --list-themes
```

## Quick start — preview every theme on one image

```bash
python scripts/frame_photos.py --preview resized/lg/heron-1.jpg \
    --name "Jane Rivers" --title "Great Blue Herons" --website "janerivers.art" \
    --year 2026 --medium "Archival pigment print" --price "$450"
```

This writes a single contact sheet to `framed/_preview_<name>.jpg` so you can
compare all themes at a glance, then pick one.

> On PowerShell, quote the price so `$` isn't treated as a variable: `--price '$450'`.

## Frame a whole folder with one theme

```bash
python scripts/frame_photos.py --theme gallery --input resized/lg --output framed \
    --name "Jane Rivers" --website "janerivers.art" --year 2026
```

Use `--theme all` to render every theme (output goes to `framed/<theme>/<name>.jpg`).

## Per-image captions (JSON manifest)

Give each file its own title/price with a manifest (`captions.json`):

```json
{
  "heron-1.jpg": { "title": "Great Blue Herons", "price": "$450" },
  "love-birds.jpg": { "title": "Love Birds", "price": "$525" }
}
```

```bash
python scripts/frame_photos.py --theme gallery --manifest captions.json \
    --name "Jane Rivers" --website "janerivers.art"
```

CLI values act as defaults; manifest fields override them per file.

## Options

| Option        | Default          | Description                                        |
| ------------- | ---------------- | -------------------------------------------------- |
| `--input`     | `../resized/lg`  | Image file or directory.                           |
| `--output`    | `../framed`      | Output directory.                                  |
| `--theme`     | `gallery`        | Theme name, or `all`.                              |
| `--preview`   | —                | Render one all-themes sheet for a single image.    |
| `--manifest`  | —                | JSON file mapping filename -> metadata fields.     |
| `--quality`   | `90`             | JPEG quality (1-100).                              |
| metadata      | —                | `--name --title --website --year --medium --price` |

## Customizing

Themes live in the `THEMES` dict in `frame_photos.py`. Each `Theme` controls
matte size/color, keyline, banner placement (`below` vs `overlay`), alignment,
accent rule, and fonts. Text layout for each theme is a small `_lines_*` builder
function that composes lines/segments from the metadata — copy one to make your
own theme. Fonts are resolved from the system font folder with fallbacks.
