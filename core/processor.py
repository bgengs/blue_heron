"""Image discovery, processing pipeline, and batch runner."""

import gc
import json
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image
from tqdm import tqdm

from core.config import (
    AUTO_COLOR_THRESHOLD,
    BASE_BG_ASSETS,
    BASE_BG_OPACITY,
    DEFAULT_INPUT_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_WATERMARK_PATH,
    JPEG_QUALITY_PRINT,
    JPEG_QUALITY_WATERMARKED,
    JPEG_QUALITY_WEB,
    MAX_WORKERS,
    OUTPUT_SUBDIRS,
    PRINT_DPI,
    REGISTRY_FILENAME,
    SUPPORTED_EXTENSIONS,
    THUMBNAIL_MAX_PX,
    WATERMARK_ASSETS,
    WEB_DPI,
    WEB_MAX_PX,
)
from core.metadata import build_copyright_exif, load_exif_bytes, save_with_exif
from core.protection import apply_web_protection, derive_photo_id, embed_dct_watermark
from core.frame import render_framed_to_path
from core.watermark import (
    apply_full_frame_overlay,
    apply_visible_watermark,
    embed_lsb_steganography,
    extract_lsb_steganography,
    generate_stego_identifier,
    load_watermark,
    pick_asset_color,
)


@dataclass
class ProcessingResult:
    """Result of processing a single image."""

    source_path: str = ""
    thumbnail_path: Optional[str] = None
    web_path: Optional[str] = None
    print_path: Optional[str] = None
    watermarked_path: Optional[str] = None
    framed_path: Optional[str] = None
    proof_path: Optional[str] = None
    raw_path: Optional[str] = None       # verbatim copy of source alongside variants
    success: bool = True
    error: Optional[str] = None
    processing_time: float = 0.0
    # --- Protection metadata (set when web variant is produced) ---
    photo_id_hex: str = ""
    phash: str = ""
    dhash: str = ""
    # --- Auto color decision (set per-photo by process_single_image) ---
    chosen_color: str = ""   # "white" | "black"


# ---------------------------------------------------------------------------
# Image Discovery
# ---------------------------------------------------------------------------

def find_images(input_dir: str) -> List[Path]:
    """Recursively discover image files in the input directory.

    Matches .jpg/.jpeg/.JPG/.JPEG extensions.
    Handles DJI subfolder structures (DJI_001/, DJI_002/, etc.)

    Args:
        input_dir: Root directory to search.

    Returns:
        Sorted list of Path objects for discovered images.
    """
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    images = []
    for ext in SUPPORTED_EXTENSIONS:
        images.extend(input_path.rglob(f"*{ext}"))

    # Deduplicate (in case .jpg and .JPG match the same file on Windows)
    seen = set()
    unique = []
    for p in sorted(images):
        resolved = p.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(p)

    return unique


def setup_output_dirs(output_dir: str) -> dict:
    """Create output directory structure.

    Creates:
        output/thumbnails/
        output/web/
        output/print/
        output/watermarked/         <- photo.jpg (DCT + visible marks)
                                       photo.png (DCT + LSB SHA-512, lossless)

    Args:
        output_dir: Root output directory.

    Returns:
        Dict mapping variant name to Path.
    """
    output_path = Path(output_dir)
    dirs = {}
    for name, subdir in OUTPUT_SUBDIRS.items():
        dir_path = output_path / subdir
        dir_path.mkdir(parents=True, exist_ok=True)
        dirs[name] = dir_path
    return dirs


def get_output_filename(source_path: Path, extension: str = ".jpg") -> str:
    """Generate output filename from source, normalizing extension.

    Args:
        source_path: Original image path.
        extension: Desired output extension (e.g., ".jpg", ".png").

    Returns:
        Filename string with normalized extension.
    """
    return source_path.stem + extension.lower()


# ---------------------------------------------------------------------------
# Image Processing Functions
# ---------------------------------------------------------------------------

def create_thumbnail(image: Image.Image) -> Image.Image:
    """Resize image to fit within 300x300 box, maintaining aspect ratio.

    For 8064x4536: result is 300x169.

    Args:
        image: Source PIL Image.

    Returns:
        Resized PIL Image in RGB mode.
    """
    thumb = image.copy()
    if thumb.mode != "RGB":
        thumb = thumb.convert("RGB")
    thumb.thumbnail((THUMBNAIL_MAX_PX, THUMBNAIL_MAX_PX), Image.LANCZOS)
    return thumb


def create_web_version(image: Image.Image) -> Image.Image:
    """Resize image to fit within 1920px max dimension.

    For 8064x4536 landscape: result is 1920x1080.
    DPI is set to 72 at save time, not here.

    Args:
        image: Source PIL Image.

    Returns:
        Resized PIL Image in RGB mode.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Calculate new dimensions maintaining aspect ratio
    max_dim = max(image.width, image.height)
    if max_dim <= WEB_MAX_PX:
        return image.copy()

    ratio = WEB_MAX_PX / max_dim
    new_width = int(image.width * ratio)
    new_height = int(image.height * ratio)
    return image.resize((new_width, new_height), Image.LANCZOS)


def create_print_version(image: Image.Image) -> Image.Image:
    """Prepare image for print — keep original resolution.

    No resize. DPI is set to 300 at save time.
    At 300 DPI, 8064x4536 = 26.9" x 15.1" print.

    Args:
        image: Source PIL Image.

    Returns:
        PIL Image in RGB mode (original resolution).
    """
    if image.mode != "RGB":
        return image.convert("RGB")
    return image.copy()


# ---------------------------------------------------------------------------
# Single Image Pipeline
# ---------------------------------------------------------------------------

def process_single_image(
    source_path: Path,
    output_dirs: dict,
    watermark_path: str = "",
    generate_proofs: bool = True,
    dry_run: bool = False,
    base_bg_path: str = "",
    color_mode: str = "auto",
    app_root: str = "",
    title: str = "",
) -> ProcessingResult:
    """Full processing pipeline for one image.

    Steps:
    1. Read source bytes and compute SHA-512
    2. Open image, extract EXIF
    3. Build copyright EXIF
    4. Pick auto color (or use forced color) -> resolve asset pair
    5. Generate all variants (thumbnail, web, print, watermarked)
    6. Save each with EXIF metadata
    7. Generate PNG proof with steganography

    Args:
        source_path: Path to source image.
        output_dirs: Dict mapping variant name to output Path.
        watermark_path: Legacy override. If non-empty, forces this exact
            watermark PNG regardless of color_mode.
        generate_proofs: Whether to generate PNG proof files.
        dry_run: If True, skip actual file writes.
        base_bg_path: Legacy override. If non-empty, forces this exact base
            overlay PNG regardless of color_mode.
        color_mode: "auto" | "white" | "black". When "auto" (default) the
            photo's mean luminance picks the asset pair. Ignored for any
            layer where a legacy path is also passed.
        app_root: Directory the relative asset paths resolve against.
            Defaults to the app directory (parent of core/).

    Returns:
        ProcessingResult with output paths, chosen color, and status.
    """
    result = ProcessingResult(source_path=str(source_path))
    start_time = time.time()

    try:
        # --- Read source and compute hash ---
        source_bytes = source_path.read_bytes()
        stego_id = generate_stego_identifier(str(source_path), source_bytes)

        # --- Load image and EXIF ---
        image = Image.open(source_path)
        if image.mode != "RGB":
            image = image.convert("RGB")
        exif_bytes = load_exif_bytes(str(source_path))

        # --- Build EXIF variants ---
        copyright_exif = build_copyright_exif(exif_bytes)
        watermarked_exif = build_copyright_exif(exif_bytes, stego_id)

        if dry_run:
            # Still record the auto decision so --dry-run reports it.
            if color_mode == "auto":
                result.chosen_color = pick_asset_color(image)
            else:
                result.chosen_color = color_mode
            result.processing_time = time.time() - start_time
            return result

        # --- Pick auto color, resolve asset pair ---
        if color_mode == "auto":
            chosen_color = pick_asset_color(image)
        else:
            chosen_color = color_mode
        result.chosen_color = chosen_color

        # Anchor relative asset paths to the app dir (parent of core/).
        root = Path(app_root) if app_root else Path(__file__).resolve().parent.parent

        resolved_wm = watermark_path or str(root / WATERMARK_ASSETS[chosen_color])
        resolved_base = base_bg_path or str(root / BASE_BG_ASSETS[chosen_color])

        # --- Load watermark + optional full-frame base (shared by web + WM) ---
        watermark = load_watermark(resolved_wm)
        base_layer = None
        if resolved_base and Path(resolved_base).exists():
            base_layer = load_watermark(resolved_base)

        # --- 1. Thumbnail ---
        thumb = create_thumbnail(image)
        thumb_path = output_dirs["thumbnails"] / get_output_filename(source_path)
        save_with_exif(thumb, str(thumb_path), copyright_exif, quality=JPEG_QUALITY_WEB)
        result.thumbnail_path = str(thumb_path)
        del thumb
        gc.collect()

        # --- 2. Web version (watermarked + Stealth Mark protection layers) ---
        # Pipeline: resize -> full-bleed base overlay -> corner watermark ->
        #           micro-mark (Layer 1) -> DCT watermark (Layer 2) -> save.
        #           Hashes (Layer 3) recorded.
        web = create_web_version(image)
        if base_layer is not None:
            web = apply_full_frame_overlay(web, base_layer, opacity=BASE_BG_OPACITY)
        web = apply_visible_watermark(web, watermark)
        web, protection_meta = apply_web_protection(
            web,
            glyph_rgba=watermark,
            source_bytes=source_bytes,
            stego_id=stego_id,
        )
        web_path = output_dirs["web"] / get_output_filename(source_path)
        save_with_exif(
            web, str(web_path), copyright_exif,
            quality=JPEG_QUALITY_WEB, dpi=(WEB_DPI, WEB_DPI),
        )
        result.web_path = str(web_path)
        result.photo_id_hex = protection_meta.photo_id_hex
        result.phash = protection_meta.phash
        result.dhash = protection_meta.dhash
        del web
        gc.collect()

        # --- 3. Print version ---
        print_img = create_print_version(image)
        print_path = output_dirs["print"] / get_output_filename(source_path)
        save_with_exif(
            print_img, str(print_path), copyright_exif,
            quality=JPEG_QUALITY_PRINT, dpi=(PRINT_DPI, PRINT_DPI),
        )
        result.print_path = str(print_path)
        del print_img
        gc.collect()

        # --- 3b. Framed banner (site display): photo + brand bar + cursive title ---
        if "framed" in output_dirs:
            framed_path = output_dirs["framed"] / get_output_filename(source_path)
            render_framed_to_path(image, framed_path, title=title)
            result.framed_path = str(framed_path)

        # --- 4. Watermarked JPEG ---
        # Pipeline: base overlay -> corner mark -> DCT hidden ID -> save.
        # NOTE: LSB stego is NOT applied to JPGs — empirically destroyed by
        # JPEG quantization at every quality level (tested q90/95/98/100,
        # subsampling=0). LSB lives on the matching PNG (step 5) which is
        # written alongside this JPG.
        wm_src = image.copy()
        if base_layer is not None:
            wm_src = apply_full_frame_overlay(wm_src, base_layer, opacity=BASE_BG_OPACITY)
        watermarked = apply_visible_watermark(wm_src, watermark)

        # Embed DCT watermark (JPEG-survivable hidden photo ID)
        wm_photo_id = derive_photo_id(source_bytes)
        wm_arr = np.asarray(watermarked, dtype=np.uint8)
        wm_arr_protected = embed_dct_watermark(wm_arr, wm_photo_id)
        watermarked = Image.fromarray(wm_arr_protected, "RGB")

        wm_path = output_dirs["watermarked"] / get_output_filename(source_path)
        save_with_exif(
            watermarked, str(wm_path), watermarked_exif,
            quality=JPEG_QUALITY_WATERMARKED,
        )
        result.watermarked_path = str(wm_path)

        # --- 5. PNG sibling with steganography (DCT + LSB SHA-512) ---
        # Written to output/watermarked/ alongside the JPG. Same basename,
        # different extension. PNG is lossless so LSB survives perfectly;
        # the DCT mark from step 4 is also present.
        if generate_proofs:
            proof_img = embed_lsb_steganography(watermarked, stego_id)
            proof_path = output_dirs["proofs"] / get_output_filename(
                source_path, extension=".png"
            )
            proof_img.save(str(proof_path), format="PNG")
            result.proof_path = str(proof_path)
            del proof_img
            gc.collect()

        del watermarked, watermark, base_layer
        gc.collect()

        # --- 6. Raw copy alongside variants ---
        # Preserves the original filename (and original case, e.g. ".JPG").
        # This is a verbatim shutil.copy2 — the raw is NOT processed, NOT
        # watermarked, NOT recompressed. The raw/ master tree is untouched.
        # Skip the copy if a matching file already exists with the same
        # mtime (idempotent re-runs don't re-copy gigabytes).
        try:
            raw_dst = output_dirs["raw"] / source_path.name
            should_copy = True
            if raw_dst.exists():
                try:
                    src_mt = source_path.stat().st_mtime
                    dst_mt = raw_dst.stat().st_mtime
                    if abs(src_mt - dst_mt) < 1.0:
                        should_copy = False
                except OSError:
                    pass  # fall through to copy
            if should_copy:
                shutil.copy2(str(source_path), str(raw_dst))
            result.raw_path = str(raw_dst)
        except Exception:
            # Non-fatal: variants are still valid even if the raw copy fails.
            # The photo isn't marked failed; raw_path simply stays None.
            pass

    except Exception as e:
        result.success = False
        result.error = str(e)

    finally:
        result.processing_time = time.time() - start_time

    return result


# ---------------------------------------------------------------------------
# Worker function for multiprocessing
# ---------------------------------------------------------------------------

def _worker(args: tuple) -> ProcessingResult:
    """Worker function for ProcessPoolExecutor.

    Receives file paths (not PIL objects) because PIL Images can't be pickled.
    Each worker loads its own watermark (39 KB, trivial).

    Args:
        args: Tuple of (source_path_str, output_dirs_str, watermark_path,
              generate_proofs, dry_run, base_bg_path, color_mode, app_root)

    Returns:
        ProcessingResult
    """
    (source_str, output_dirs_str, watermark_path, generate_proofs,
     dry_run, base_bg_path, color_mode, app_root) = args

    # Reconstruct Path objects
    source_path = Path(source_str)
    output_dirs = {k: Path(v) for k, v in output_dirs_str.items()}

    return process_single_image(
        source_path,
        output_dirs,
        watermark_path,
        generate_proofs,
        dry_run,
        base_bg_path=base_bg_path,
        color_mode=color_mode,
        app_root=app_root,
    )


# ---------------------------------------------------------------------------
# Batch Processing
# ---------------------------------------------------------------------------

def process_batch(
    image_paths: List[Path],
    output_dirs: dict,
    watermark_path: str = "",
    max_workers: int = MAX_WORKERS,
    generate_proofs: bool = True,
    dry_run: bool = False,
    base_bg_path: str = "",
    color_mode: str = "auto",
    app_root: str = "",
) -> List[ProcessingResult]:
    """Process all images with progress bar and multiprocessing.

    Uses ProcessPoolExecutor for true parallelism (bypasses GIL
    for CPU-bound image processing).

    Args:
        image_paths: List of source image Paths.
        output_dirs: Dict mapping variant name to output Path.
        watermark_path: Legacy override for the corner watermark PNG.
            Empty (the new default) means: let color_mode pick from the
            assets/bg-{white,black}.png pair per photo.
        max_workers: Number of parallel workers.
        generate_proofs: Whether to generate PNG proof files.
        dry_run: If True, skip actual file writes.
        base_bg_path: Legacy override for the base overlay. Empty means
            color_mode picks from assets/base-bg-{white,black}.png per photo.
        color_mode: "auto" | "white" | "black" (default "auto").
        app_root: Directory relative asset paths resolve against.

    Returns:
        List of ProcessingResult objects.
    """
    # Convert Path objects to strings for pickling
    output_dirs_str = {k: str(v) for k, v in output_dirs.items()}

    # Build work items
    work_items = [
        (str(p), output_dirs_str, watermark_path, generate_proofs,
         dry_run, base_bg_path, color_mode, app_root)
        for p in image_paths
    ]

    results = []

    if max_workers <= 1:
        # Sequential mode
        for item in tqdm(work_items, desc="Processing images", unit="img"):
            result = _worker(item)
            results.append(result)
    else:
        # Parallel mode
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_worker, item): item[0]
                for item in work_items
            }

            with tqdm(total=len(futures), desc="Processing images", unit="img") as pbar:
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    pbar.update(1)

                    if not result.success:
                        pbar.write(
                            f"  FAILED: {Path(result.source_path).name} "
                            f"- {result.error}"
                        )

    return results


# ---------------------------------------------------------------------------
# Protection Registry
# ---------------------------------------------------------------------------

def write_protection_registry(
    results: List[ProcessingResult],
    web_dir: Path,
) -> Path:
    """Merge results with any existing registry.json and write it back.

    The registry is an append-style record of every web-published photo's
    perceptual hashes and DCT watermark ID. publish.py copies this file to
    the web app so the same data is available alongside photos.json.

    Args:
        results: ProcessingResult objects from a completed batch.
        web_dir: Path to output/web/ directory.

    Returns:
        Path to the written registry.json file.
    """
    registry_path = web_dir / REGISTRY_FILENAME

    # Load existing entries (so partial reruns don't lose history)
    existing: dict = {}
    if registry_path.exists():
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry in data.get("photos", []):
                    if "filename" in entry:
                        existing[entry["filename"]] = entry
        except (OSError, json.JSONDecodeError):
            pass

    # Merge in new results (only entries with a web_path + protection data)
    for r in results:
        if not r.success or not r.web_path or not r.photo_id_hex:
            continue
        filename = Path(r.web_path).name
        existing[filename] = {
            "filename": filename,
            "photo_id_hex": r.photo_id_hex,
            "phash": r.phash,
            "dhash": r.dhash,
            "chosen_color": r.chosen_color,
            "processed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_basename": Path(r.source_path).name,
        }

    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(existing),
        "photos": sorted(existing.values(), key=lambda e: e["filename"]),
    }

    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return registry_path
