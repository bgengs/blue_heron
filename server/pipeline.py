"""Glue between raw/, the core protection pipeline, output/, and the site.

Mirrors the eagle app's admin/actions.py: sequential processing so the job
can report per-image progress, then a publish step that copies protected web
variants into the static site and updates the photo manifest.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import edits, photo_catalog, settings, store
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

    photo_catalog.clear_cache()
    cat = photo_catalog.catalog_stats()
    if cat["exists"]:
        job.log(f"photo_catalog.json: {cat['entries']} lookup keys — titles/descriptions applied on Process.")
    else:
        job.log("No photo_catalog.json — titles come from Editor only.")

    job.set_progress(0, len(images), "Preparing output directories")
    output_dirs = setup_output_dirs(str(settings.OUTPUT_DIR))
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    results, ok, failed, titled = [], 0, 0, 0
    for i, img in enumerate(images):
        if job.cancel_flag.is_set():
            job.status = "cancelled"
            job.log("Cancelled.")
            return
        job.set_progress(i, len(images), f"Processing {img.name}")

        # Catalog titles/descriptions (Claude) + any crop/rotate from Editor.
        source = img
        edit = edits.get_edit(img.name)
        before_title = (edit.get("title") or "").strip()
        edit = photo_catalog.apply_to_edit(img.name, edit, overwrite=True)
        if (edit.get("title") or "").strip() and (edit.get("title") or "").strip() != before_title:
            titled += 1
        # Persist so Editor / Publish / framed banners see the same copy.
        if edit.get("title") or edit.get("caption"):
            edits.save_edit(
                img.name,
                title=str(edit.get("title") or ""),
                caption=str(edit.get("caption") or ""),
                crop=edit.get("crop"),
                rotate=int(edit.get("rotate") or 0),
            )

        edited = edits.apply_edits_to_image(img, edit)
        if edited is not None:
            source = WORK_DIR / f"{img.stem}.jpg"
            edited.save(source, "JPEG", quality=95)
            job.log(f"  applied crop/rotate to {img.name}")

        title = str(edit.get("title") or "")
        if title:
            job.log(f"  title: {title}")

        result = process_single_image(
            source, output_dirs,
            generate_proofs=generate_proofs,
            color_mode="auto",
            app_root=str(settings.APP_ROOT),
            title=title,
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
    job.log(f"Catalog titles applied/updated: {titled}")
    job.set_progress(len(images), len(images), f"Done. {ok} ok, {failed} failed.")
    job.result = {"images": len(images), "succeeded": ok, "failed": failed, "catalog_titles": titled}


# ---------------- publish job ----------------

def run_publish(job: Job) -> None:
    """Copy protected web/thumb/print/framed variants into web/, update manifest.

    Only ADDS or REFRESHES files — never deletes site images. New photos get
    a manifest entry with active=False (hidden until you tick Live on Photos).
    Re-publish does not flip Live on/off. Titles/captions come from the Editor
    / photo_catalog. Print + framed land in web/images/ for Prodigi and share.
    """
    web_src = settings.OUTPUT_DIR / "web"
    thumb_src = settings.OUTPUT_DIR / "thumbnails"
    print_src = settings.OUTPUT_DIR / "print"
    framed_src = settings.OUTPUT_DIR / "framed"
    if not web_src.exists():
        raise FileNotFoundError("Nothing processed yet — run Process first.")

    settings.SITE_WEB_IMAGES.mkdir(parents=True, exist_ok=True)
    settings.SITE_THUMB_IMAGES.mkdir(parents=True, exist_ok=True)
    settings.SITE_PRINT_IMAGES.mkdir(parents=True, exist_ok=True)
    settings.SITE_FRAMED_IMAGES.mkdir(parents=True, exist_ok=True)

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
        print_file = print_src / f.name
        if print_file.exists():
            shutil.copy2(print_file, settings.SITE_PRINT_IMAGES / f.name)
        framed_file = framed_src / f.name
        if framed_file.exists():
            shutil.copy2(framed_file, settings.SITE_FRAMED_IMAGES / f.name)

        slug = edits.slug_for(f.name)
        edit = edits.get_edit(f.name)
        fields = {"file": f.name}
        # Only seed title/caption on first publish, or when the editor set them,
        # so re-publishing never clobbers titles edited on the Photos page.
        if edit.get("title"):
            fields["title"] = edit["title"]
        if edit.get("caption"):
            fields["caption"] = edit["caption"]
        # Default Live: Photoshop crops (gbh_fly_*) on; raw DJI / others off.
        # Re-publish never flips an existing Live flag.
        if new:
            fields["active"] = f.name.lower().startswith("gbh_fly")
        store.upsert_photo(slug, **fields)
        if new:
            added += 1
            state = "Live" if fields["active"] else "hidden"
            job.log(f"  + {f.name} ({state})")
        else:
            refreshed += 1
        job.set_progress(i + 1, len(web_files), f.name)

    # Ship the protection registry alongside the site for later verification.
    registry = web_src / "registry.json"
    if registry.exists():
        shutil.copy2(registry, settings.DATA_DIR / "registry.json")

    job.log(f"Published: {added} new, {refreshed} refreshed (gbh_fly_* default Live).")
    job.result = {"added": added, "refreshed": refreshed}
