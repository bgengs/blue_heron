"""EXIF metadata preservation and copyright injection using piexif."""

import piexif
from PIL import Image
from typing import Optional
from core.config import COPYRIGHT_TEXT, COPYRIGHT_ARTIST


def load_exif_bytes(source_path: str) -> bytes:
    """Read raw EXIF bytes from a source image file.

    Args:
        source_path: Path to the source JPEG/MPO image.

    Returns:
        Raw EXIF bytes, or empty bytes if no EXIF found.
    """
    try:
        img = Image.open(source_path)
        exif_data = img.info.get("exif", b"")
        img.close()
        return exif_data
    except Exception:
        return b""


def build_copyright_exif(
    original_exif_bytes: bytes,
    stego_identifier: Optional[str] = None,
) -> bytes:
    """Add copyright fields to existing EXIF data.

    Takes original EXIF bytes, injects copyright/artist tags,
    and optionally embeds the steganography identifier in UserComment.

    Args:
        original_exif_bytes: Raw EXIF bytes from source image.
        stego_identifier: Optional steganography identifier string
            to embed in EXIF UserComment field.

    Returns:
        New EXIF bytes with copyright fields added.
    """
    if original_exif_bytes:
        try:
            exif_dict = piexif.load(original_exif_bytes)
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
    else:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

    # Set copyright and artist in IFD0
    exif_dict["0th"][piexif.ImageIFD.Copyright] = COPYRIGHT_TEXT.encode("utf-8")
    exif_dict["0th"][piexif.ImageIFD.Artist] = COPYRIGHT_ARTIST.encode("utf-8")

    # Embed stego identifier in UserComment if provided
    if stego_identifier:
        # UserComment requires charset prefix per EXIF spec
        user_comment = b"ASCII\x00\x00\x00" + stego_identifier.encode("ascii")
        exif_dict["Exif"][piexif.ExifIFD.UserComment] = user_comment

    try:
        return piexif.dump(exif_dict)
    except Exception as e:
        # If EXIF dump fails (e.g., corrupt data), build minimal EXIF
        minimal = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
        minimal["0th"][piexif.ImageIFD.Copyright] = COPYRIGHT_TEXT.encode("utf-8")
        minimal["0th"][piexif.ImageIFD.Artist] = COPYRIGHT_ARTIST.encode("utf-8")
        if stego_identifier:
            user_comment = b"ASCII\x00\x00\x00" + stego_identifier.encode("ascii")
            minimal["Exif"][piexif.ExifIFD.UserComment] = user_comment
        return piexif.dump(minimal)


def save_with_exif(
    image: Image.Image,
    output_path: str,
    exif_bytes: bytes,
    quality: int = 95,
    dpi: Optional[tuple] = None,
) -> None:
    """Save a PIL Image as JPEG with EXIF data and optional DPI.

    Args:
        image: PIL Image in RGB mode.
        output_path: Destination file path.
        exif_bytes: Raw EXIF bytes to embed.
        quality: JPEG compression quality (1-100).
        dpi: Optional (x_dpi, y_dpi) tuple.
    """
    # Ensure RGB mode for JPEG
    if image.mode != "RGB":
        image = image.convert("RGB")

    save_kwargs = {
        "format": "JPEG",
        "quality": quality,
        "subsampling": 0,  # 4:4:4 for best quality
    }

    if exif_bytes:
        save_kwargs["exif"] = exif_bytes

    if dpi:
        save_kwargs["dpi"] = dpi

    image.save(output_path, **save_kwargs)
