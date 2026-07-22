"""Glue between raw/, the core protection pipeline, output/, and the site.

Mirrors the eagle app's admin/actions.py: sequential processing so the job
can report per-image progress, then a publish step that copies protected web
variants into the static site and updates the photo manifest.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import edits, settings, store
from .jobs import Job

VARIANT_DIRS = ("thumbnails", "web", "print", "watermarked")
WORK_DIR = settings.OUTPUT_DIR / "_work"


# ---------------- raw scanning ----------------

@dataclass
class RawFolder:
    name: str          # "" means loose files at raw/ root
    label: str
    image_count: int
    processed_count: int


def _count_processed(images: list[Path]) -> int:
    web = settings.OUTPUT_DIR / "web"
    if not web.exists():
        return 0
    return sum(1 for p in images if (web / f"{p.stem}.jpg").exists())


def scan_raw() -> list[RawFolder]:
    from core.processor import find_images

    settings.RAW_DIR.mkdir(exist_ok=True)
    folders: list[RawFolder] = []

    loose = [
        p for p in sorted(settings.RAW_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg")
    ]
    if loose:
        folders.append(RawFolder("", "(loose files)", len(loose), _count_processed(loose)))

    for sub in sorted(settings.RAW_DIR.iterdir()):
        if sub.is_dir():
            images = find_images(str(sub))
            folders.append(RawFolder(sub.name, sub.name, len(images), _count_processed(images)))
    return folders


# ---------------- processing job ----------------

def run_process(job: Job, folder_name: str = "", generate_proofs: bool = True) -> None:
    """Process raw/<folder>/ (or loose files at raw/ root) into output/."""
    from core.processor import (
        find_images,
        process_single_image,
        setup_output_dirs,
        write_protection_registry,
    )

    if folder_name:
        src = settings.RAW_DIR / folder_name
        if not src.exists():
            raise FileNotFoundError(f"Folder not found: {src}")
        images = find_images(str(src))
    else:
        images = [
            p for p in sorted(settings.RAW_DIR.iterdir())
            if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg")
        ]

    job.log(f"Found {len(images)} images.")
    if not images:
        job.result = {"images": 0}
        return

    job.set_progress(0, len(images), "Preparing output directories")
    output_dirs = setup_output_dirs(str(settings.OUTPUT_DIR))
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    results, ok, failed = [], 0, 0
    for i, img in enumerate(images):
        if job.cancel_flag.is_set():
            job.status = "cancelled"
            job.log("Cancelled.")
            return
        job.set_progress(i, len(images), f"Processing {img.name}")

        # Apply non-destructive crop/rotate from the editor, if any. The
        # cropped copy (same stem) is what gets protected + published; the
        # original in raw/ is never modified.
        source = img
        edit = edits.get_edit(img.name)
        edited = edits.apply_edits_to_image(img, edit)
        if edited is not None:
            source = WORK_DIR / f"{img.stem}.jpg"
            edited.save(source, "JPEG", quality=95)
            job.log(f"  applied crop/rotate to {img.name}")

        result = process_single_image(
            source, output_dirs,
            generate_proofs=generate_proofs,
            color_mode="auto",
            app_root=str(settings.APP_ROOT),
        )
        results.append(result)
        if result.success:
            ok += 1
            job.log(f"  OK  {img.name}  ({result.processing_time:.1f}s)")
        else:
            failed += 1
            job.log(f"  FAIL {img.name} — {result.error}")

    registry = write_protection_registry(results, settings.OUTPUT_DIR / "web")
    job.log(f"Registry updated: {registry}")
    job.set_progress(len(images), len(images), f"Done. {ok} ok, {failed} failed.")
    job.result = {"images": len(images), "succeeded": ok, "failed": failed}


# ---------------- publish job ----------------

def run_publish(job: Job) -> None:
    """Copy protected web variants + thumbnails into site/, update manifest.

    Only ADDS or REFRESHES files — never deletes site images. New photos get
    a manifest entry (active by default) so they appear in the gallery;
    titles/captions are edited in the admin Photos page.
    """
    web_src = settings.OUTPUT_DIR / "web"
    thumb_src = settings.OUTPUT_DIR / "thumbnails"
    if not web_src.exists():
        raise FileNotFoundError("Nothing processed yet — run Process first.")

    settings.SITE_WEB_IMAGES.mkdir(parents=True, exist_ok=True)
    settings.SITE_THUMB_IMAGES.mkdir(parents=True, exist_ok=True)

    web_files = sorted(web_src.glob("*.jpg"))
    job.set_progress(0, len(web_files), "Publishing")
    added, refreshed = 0, 0
    for i, f in enumerate(web_files):
        dest = settings.SITE_WEB_IMAGES / f.name
        new = not dest.exists()
        shutil.copy2(f, dest)
        thumb = thumb_src / f.name
        if thumb.exists():
            shutil.copy2(thumb, settings.SITE_THUMB_IMAGES / f.name)

        slug = edits.slug_for(f.name)
        edit = edits.get_edit(f.name)
        fields = {"file": f.name}
        # Only seed title/caption on first publish, or when the editor set them,
        # so re-publishing never clobbers titles edited on the Photos page.
        if edit.get("title"):
            fields["title"] = edit["title"]
        if edit.get("caption"):
            fields["caption"] = edit["caption"]
        store.upsert_photo(slug, **fields)
        if new:
            added += 1
            job.log(f"  + {f.name}")
        else:
            refreshed += 1
        job.set_progress(i + 1, len(web_files), f.name)

    # Ship the protection registry alongside the site for later verification.
    registry = web_src / "registry.json"
    if registry.exists():
        shutil.copy2(registry, settings.DATA_DIR / "registry.json")

    job.log(f"Published: {added} new, {refreshed} refreshed.")
    job.result = {"added": added, "refreshed": refreshed}
