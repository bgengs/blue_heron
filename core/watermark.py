"""Visible watermark compositing and LSB steganography."""

import hashlib
import struct
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from PIL import Image

from core.config import (
    AUTO_COLOR_THRESHOLD,
    BASE_BG_OPACITY,
    STEGO_PREFIX,
    WATERMARK_OPACITY,
    WATERMARK_PADDING,
    WATERMARK_SCALE,
)


# ---------------------------------------------------------------------------
# Auto Color Selection
# ---------------------------------------------------------------------------

def pick_asset_color(
    image: Image.Image,
    threshold: int = AUTO_COLOR_THRESHOLD,
) -> str:
    """Pick 'white' or 'black' asset variant from a photo's mean luminance.

    Downscales the image to a 128px thumbnail (cheap, ~1 ms) and computes
    mean perceptual luminance Y = 0.299R + 0.587G + 0.114B on the 0-255
    scale. Dark photos (Y < threshold) take the white asset pair so the
    marks read; bright photos take the black pair.

    Args:
        image: Source PIL Image.
        threshold: Mean Y boundary (default AUTO_COLOR_THRESHOLD = 128).

    Returns:
        "white" or "black".
    """
    sample = image.copy()
    sample.thumbnail((128, 128), Image.LANCZOS)
    if sample.mode != "RGB":
        sample = sample.convert("RGB")
    arr = np.asarray(sample, dtype=np.float32)
    y = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    mean_y = float(y.mean())
    return "white" if mean_y < threshold else "black"


# ---------------------------------------------------------------------------
# Visible Watermark
# ---------------------------------------------------------------------------

def load_watermark(watermark_path: str) -> Image.Image:
    """Load watermark PNG as RGBA image.

    Args:
        watermark_path: Path to watermark PNG file (must have alpha channel).

    Returns:
        PIL Image in RGBA mode.

    Raises:
        FileNotFoundError: If watermark file doesn't exist.
        ValueError: If image cannot be converted to RGBA.
    """
    wm = Image.open(watermark_path)
    if wm.mode != "RGBA":
        wm = wm.convert("RGBA")
    return wm


def resize_watermark(watermark: Image.Image, target_width: int) -> Image.Image:
    """Resize watermark maintaining aspect ratio.

    Args:
        watermark: RGBA PIL Image.
        target_width: Desired width in pixels.

    Returns:
        Resized RGBA PIL Image.
    """
    aspect = watermark.height / watermark.width
    target_height = int(target_width * aspect)
    return watermark.resize((target_width, target_height), Image.LANCZOS)


def apply_visible_watermark(
    image: Image.Image,
    watermark: Image.Image,
    scale: float = WATERMARK_SCALE,
    opacity: float = WATERMARK_OPACITY,
    padding: int = WATERMARK_PADDING,
) -> Image.Image:
    """Composite watermark onto image in bottom-right corner.

    Algorithm:
    1. Calculate target watermark size (scale % of image width)
    2. Resize watermark with LANCZOS
    3. Adjust alpha channel by opacity factor
    4. Position in bottom-right with padding
    5. Composite using alpha_composite

    Args:
        image: Source PIL Image (RGB or RGBA).
        watermark: Watermark PIL Image (RGBA).
        scale: Watermark width as fraction of image width (0.0-1.0).
        opacity: Watermark opacity (0.0-1.0).
        padding: Pixels from edges.

    Returns:
        New RGB image with watermark composited.
    """
    # Ensure image is RGBA for compositing
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    # Resize watermark to target size
    target_width = int(image.width * scale)
    wm = resize_watermark(watermark, target_width)

    # Adjust watermark opacity
    r, g, b, a = wm.split()
    a = a.point(lambda x: int(x * opacity))
    wm = Image.merge("RGBA", (r, g, b, a))

    # Calculate bottom-right position
    x = image.width - wm.width - padding
    y = image.height - wm.height - padding

    # Create transparent overlay and paste watermark
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay.paste(wm, (x, y))

    # Composite and convert back to RGB
    result = Image.alpha_composite(image, overlay)
    return result.convert("RGB")


def apply_full_frame_overlay(
    image: Image.Image,
    overlay: Image.Image,
    opacity: float = BASE_BG_OPACITY,
) -> Image.Image:
    """Stretch overlay to the image's width and height, then alpha-composite.

    Use for a full-bleed film (e.g. base-bg.png) under corner watermarks.

    Args:
        image: Source PIL Image (RGB or RGBA).
        overlay: PIL Image (RGBA preferred); resized to match image dimensions.
        opacity: Multiplier for the overlay alpha channel after resize.
            1.0 leaves the PNG as-authored. Use values above 1.0 to strengthen
            very faint alpha (each channel is clamped to 255).

    Returns:
        RGB image with overlay applied.
    """
    if image.mode != "RGBA":
        base = image.convert("RGBA")
    else:
        base = image.copy()

    ov = overlay.convert("RGBA").resize((base.width, base.height), Image.LANCZOS)
    o = float(opacity)
    if o != 1.0:
        r, g, b, a = ov.split()
        a = a.point(lambda x, op=o: min(255, max(0, int(round(x * op)))))
        ov = Image.merge("RGBA", (r, g, b, a))

    out = Image.alpha_composite(base, ov)
    return out.convert("RGB")


# ---------------------------------------------------------------------------
# LSB Steganography
# ---------------------------------------------------------------------------

def generate_stego_identifier(source_path: str, source_bytes: bytes = None) -> str:
    """Generate a steganography identifier string.

    Format: BERNIEGENGEL|<iso_timestamp>|<sha512_hash>

    The SHA-512 hash is computed from the original file bytes,
    providing a cryptographic link back to the source file.

    Args:
        source_path: Path to the original image file.
        source_bytes: Pre-read bytes of the original file (avoids re-read).

    Returns:
        Identifier string, e.g.:
        "BERNIEGENGEL|2026-05-10T14:30:00Z|ee26b0dd..."
    """
    if source_bytes is None:
        with open(source_path, "rb") as f:
            source_bytes = f.read()

    file_hash = hashlib.sha512(source_bytes).hexdigest()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return f"{STEGO_PREFIX}|{timestamp}|{file_hash}"


def embed_lsb_steganography(image: Image.Image, message: str) -> Image.Image:
    """Embed message into image using LSB steganography in the red channel.

    Algorithm:
    1. Encode message as UTF-8 bytes
    2. Prepend 32-bit big-endian length header
    3. Convert entire payload to bit array
    4. Modify LSB of red channel for first N pixels (row-major order)

    The message typically occupies ~1,320 pixels out of 36M+,
    which is visually imperceptible (0.004% of pixels).

    IMPORTANT: The output image MUST be saved as PNG (lossless).
    JPEG compression will destroy the embedded data.

    Args:
        image: PIL Image (RGB mode).
        message: String to embed.

    Returns:
        New PIL Image with steganography embedded.

    Raises:
        ValueError: If message is too long for the image.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Encode message
    msg_bytes = message.encode("utf-8")
    length_header = struct.pack(">I", len(msg_bytes))  # 4 bytes, big-endian
    payload = length_header + msg_bytes

    # Convert payload to bit array
    bits = []
    for byte in payload:
        for bit_pos in range(7, -1, -1):
            bits.append((byte >> bit_pos) & 1)

    # Check capacity
    pixels = np.array(image)
    total_pixels = pixels.shape[0] * pixels.shape[1]
    if len(bits) > total_pixels:
        raise ValueError(
            f"Message too long: needs {len(bits)} pixels, "
            f"image has {total_pixels}"
        )

    # Flatten red channel and modify LSBs
    flat = pixels[:, :, 0].flatten()
    for i, bit in enumerate(bits):
        flat[i] = (flat[i] & 0xFE) | bit

    # Reshape and rebuild image
    pixels[:, :, 0] = flat.reshape(pixels.shape[0], pixels.shape[1])
    return Image.fromarray(pixels, "RGB")


def extract_lsb_steganography(image: Image.Image) -> Optional[str]:
    """Extract LSB steganography message from image.

    Algorithm:
    1. Read LSBs from first 32 pixels' red channel -> 4-byte length header
    2. Read LSBs from next (length * 8) pixels -> message bytes
    3. Decode UTF-8 and validate prefix

    Args:
        image: PIL Image (RGB mode), saved as lossless PNG.

    Returns:
        Extracted message string, or None if no valid message found.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    pixels = np.array(image)
    flat = pixels[:, :, 0].flatten()

    try:
        # Read 32-bit length header (first 32 pixels)
        length_bits = []
        for i in range(32):
            length_bits.append(flat[i] & 1)

        length_bytes = bytearray()
        for i in range(0, 32, 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | length_bits[i + j]
            length_bytes.append(byte)

        msg_length = struct.unpack(">I", bytes(length_bytes))[0]

        # Sanity check: message shouldn't be absurdly long
        max_reasonable = min(10000, (len(flat) - 32) // 8)
        if msg_length > max_reasonable or msg_length == 0:
            return None

        # Read message bits
        msg_bits = []
        offset = 32  # Start after length header
        for i in range(msg_length * 8):
            msg_bits.append(flat[offset + i] & 1)

        # Convert bits to bytes
        msg_bytes = bytearray()
        for i in range(0, len(msg_bits), 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | msg_bits[i + j]
            msg_bytes.append(byte)

        message = msg_bytes.decode("utf-8")

        # Validate prefix
        if not message.startswith(STEGO_PREFIX + "|"):
            return None

        return message

    except (IndexError, UnicodeDecodeError, struct.error):
        return None
