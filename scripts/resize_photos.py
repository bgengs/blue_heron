#!/usr/bin/env python3
"""Resize photos into responsive size variants (xs, sm, md, lg, xl).

Downscales high-resolution source images into several web-friendly widths
while preserving aspect ratio and image quality. Uses high-quality Lanczos
resampling, honors EXIF orientation, and preserves the embedded ICC color
profile so colors stay accurate.

Usage examples:
    python resize_photos.py
    python resize_photos.py --input ../source_photos --output ../resized
    python resize_photos.py --formats jpeg webp --quality 82
    python resize_photos.py --sizes xs=480 sm=768 md=1280 lg=1920 xl=2560
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

# Default responsive breakpoints (target width in pixels). Height is derived
# automatically to keep the original aspect ratio.
DEFAULT_SIZES: dict[str, int] = {
    "xs": 480,
    "sm": 768,
    "md": 1280,
    "lg": 1920,
    "xl": 2560,
}

# Source file extensions we know how to open.
SOURCE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}

# Extension used on disk for each output format.
FORMAT_EXTENSION = {
    "jpeg": ".jpg",
    "webp": ".webp",
    "png": ".png",
}


def parse_sizes(pairs: list[str]) -> dict[str, int]:
    """Parse ``name=width`` CLI pairs into an ordered dict of sizes."""
    sizes: dict[str, int] = {}
    for pair in pairs:
        if "=" not in pair:
            raise argparse.ArgumentTypeError(
                f"Invalid size '{pair}'. Expected format name=width, e.g. md=1280."
            )
        name, _, raw_width = pair.partition("=")
        name = name.strip()
        try:
            width = int(raw_width)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"Invalid width for '{name}': '{raw_width}' is not an integer."
            ) from exc
        if width <= 0:
            raise argparse.ArgumentTypeError(f"Width for '{name}' must be positive.")
        sizes[name] = width
    return sizes


def human_size(num_bytes: int) -> str:
    """Return a compact human-readable byte size."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def save_variant(
    image: Image.Image,
    dest: Path,
    fmt: str,
    quality: int,
    icc_profile: bytes | None,
) -> None:
    """Save ``image`` to ``dest`` using the given format and quality."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    save_kwargs: dict = {}
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile

    if fmt == "jpeg":
        out = image
        if out.mode not in ("RGB", "L"):
            out = out.convert("RGB")
        out.save(
            dest,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
            subsampling="4:2:0",
            **save_kwargs,
        )
    elif fmt == "webp":
        image.save(
            dest,
            format="WEBP",
            quality=quality,
            method=6,
            **save_kwargs,
        )
    elif fmt == "png":
        image.save(dest, format="PNG", optimize=True, **save_kwargs)
    else:  # pragma: no cover - guarded by argparse choices
        raise ValueError(f"Unsupported format: {fmt}")


def resize_to_width(image: Image.Image, target_width: int) -> Image.Image:
    """Return a copy of ``image`` scaled to ``target_width`` (aspect preserved)."""
    src_width, src_height = image.size
    target_height = max(1, round(src_height * target_width / src_width))
    return image.resize((target_width, target_height), Image.Resampling.LANCZOS)


def process_image(
    src_path: Path,
    output_dir: Path,
    sizes: dict[str, int],
    formats: list[str],
    quality: int,
    allow_upscale: bool,
    group_by: str,
    overwrite: bool,
) -> int:
    """Generate all size/format variants for a single source image.

    Returns the number of variants written.
    """
    written = 0
    try:
        with Image.open(src_path) as raw:
            # Apply EXIF orientation so rotated phone photos come out upright.
            image = ImageOps.exif_transpose(raw)
            icc_profile = image.info.get("icc_profile")
            src_width = image.width
            stem = src_path.stem
            print(f"{src_path.name} ({image.width}x{image.height})")

            for name, target_width in sizes.items():
                width = target_width
                if width > src_width and not allow_upscale:
                    # Cap at the source width to avoid quality loss from upscaling.
                    width = src_width

                variant = resize_to_width(image, width)

                for fmt in formats:
                    ext = FORMAT_EXTENSION[fmt]
                    if group_by == "size":
                        dest = output_dir / name / f"{stem}{ext}"
                    else:  # group_by == "name"
                        dest = output_dir / stem / f"{stem}-{name}{ext}"

                    if dest.exists() and not overwrite:
                        print(f"    skip (exists): {dest}")
                        continue

                    save_variant(variant, dest, fmt, quality, icc_profile)
                    print(
                        f"    {name:<3} {variant.width}x{variant.height} "
                        f"-> {dest} ({human_size(dest.stat().st_size)})"
                    )
                    written += 1
    except Exception as exc:  # noqa: BLE001 - report and continue with next file
        print(f"  ERROR processing {src_path.name}: {exc}", file=sys.stderr)
    return written


def collect_sources(input_dir: Path) -> list[Path]:
    """Return sorted image files in ``input_dir`` we know how to process."""
    return sorted(
        p
        for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SOURCE_EXTENSIONS
    )


def build_parser() -> argparse.ArgumentParser:
    script_dir = Path(__file__).resolve().parent
    default_input = script_dir.parent / "source_photos"
    default_output = script_dir.parent / "resized"

    parser = argparse.ArgumentParser(
        description="Resize photos into responsive variants (xs, sm, md, lg, xl).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help="Directory containing source images.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help="Directory to write resized variants into.",
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        metavar="NAME=WIDTH",
        default=None,
        help="Space-separated size definitions, e.g. xs=480 sm=768 md=1280.",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=sorted(FORMAT_EXTENSION),
        default=["jpeg"],
        help="Output formats to generate.",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=85,
        help="Output quality for lossy formats (1-100). 82-88 keeps quality high.",
    )
    parser.add_argument(
        "--group-by",
        choices=["size", "name"],
        default="size",
        help="Folder layout: 'size' -> output/md/photo.jpg, 'name' -> output/photo/photo-md.jpg.",
    )
    parser.add_argument(
        "--allow-upscale",
        action="store_true",
        help="Allow enlarging images beyond their source width (off by default).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files instead of skipping them.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not (1 <= args.quality <= 100):
        print("--quality must be between 1 and 100.", file=sys.stderr)
        return 2

    sizes = parse_sizes(args.sizes) if args.sizes else dict(DEFAULT_SIZES)

    input_dir: Path = args.input
    output_dir: Path = args.output

    if not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    sources = collect_sources(input_dir)
    if not sources:
        print(f"No source images found in {input_dir}", file=sys.stderr)
        return 1

    print(f"Input:   {input_dir}")
    print(f"Output:  {output_dir}")
    print(f"Sizes:   {', '.join(f'{k}={v}' for k, v in sizes.items())}")
    print(f"Formats: {', '.join(args.formats)} (quality {args.quality})")
    print(f"Found {len(sources)} source image(s).\n")

    total_written = 0
    for src in sources:
        total_written += process_image(
            src_path=src,
            output_dir=output_dir,
            sizes=sizes,
            formats=args.formats,
            quality=args.quality,
            allow_upscale=args.allow_upscale,
            group_by=args.group_by,
            overwrite=args.overwrite,
        )

    print(f"\nDone. Wrote {total_written} variant(s) to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
