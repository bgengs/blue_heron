"""Configuration constants for drone photography processing."""

import os

# --- Directories ---
DEFAULT_INPUT_DIR = "raw"
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_WATERMARK_PATH = "assets/bgg.png"
DEFAULT_BASE_BG_PATH = "assets/base-bg.png"

# Auto-color asset pairs. process_single_image picks one based on the photo's
# mean luminance and uses the matching pair for BOTH the corner watermark and
# the full-bleed base overlay (they always match).
WATERMARK_ASSETS = {
    "white": "assets/bg-white.png",
    "black": "assets/bg-black.png",
}
BASE_BG_ASSETS = {
    "white": "assets/base-bg-white.png",
    "black": "assets/base-bg-black.png",
}
# Mean perceptual Y below this -> photo is "dark" -> use white assets.
# Y is on the 0-255 scale.
AUTO_COLOR_THRESHOLD = 128

# Full-bleed overlay on web + watermarked JPGs (before corner watermark).
# Multiplies overlay alpha after resize; clamped to 255. Use >1.0 if the PNG
# has very low alpha. Lower = subtler wash on the photo.
BASE_BG_OPACITY = 5.0

OUTPUT_SUBDIRS = {
    "thumbnails": "thumbnails",
    "web": "web",
    "print": "print",
    "watermarked": "watermarked",
    # Raw copy of the original source file. The raw/ tree remains the
    # canonical master archive — this is a per-album COPY so each output
    # album is self-contained, and the raw rides along with the variants
    # through editor move/copy/archive operations.
    "raw": "raw",
    # Proof PNGs (lossless, carry LSB SHA-512) sit ALONGSIDE the watermarked
    # JPGs in the same folder. Each photo gets:  photo.jpg + photo.png
    "proofs": "watermarked",
}

# --- Image Size Constraints ---
THUMBNAIL_MAX_PX = 300
WEB_MAX_PX = 1600              # Lowered from 1920 (print-killer: too small for >5x7 print)
WEB_DPI = 72
PRINT_DPI = 300

# --- JPEG Quality ---
JPEG_QUALITY_WEB = 78          # Lowered from 85 (print-killer; still gorgeous on screen)
JPEG_QUALITY_PRINT = 95
JPEG_QUALITY_WATERMARKED = 95

# --- Protection Registry ---
# Written to output/web/registry.json by the batch processor, then copied to
# the web app by publish.py. Used to prove "this online photo is mine" via
# perceptual hash lookup + DCT watermark extraction.
REGISTRY_FILENAME = "registry.json"

# --- Watermark Settings ---
WATERMARK_OPACITY = 0.82       # corner bgg.png strength (higher = darker / more solid)
WATERMARK_SCALE = 0.15         # 15% of image width
WATERMARK_PADDING = 20         # pixels from edges
WATERMARK_POSITION = "bottom-right"

# --- Steganography Settings ---
STEGO_PREFIX = "BERNIEGENGEL"
STEGO_HASH_ALGORITHM = "sha512"
STEGO_LENGTH_BITS = 32         # 32-bit length header

# --- Copyright ---
COPYRIGHT_TEXT = "\u00a9 2026 Bernie Gengel Photography - blueheron.gallery"
COPYRIGHT_ARTIST = "Bernie Gengel"
COPYRIGHT_URL = "https://blueheron.gallery"

# --- File Discovery ---
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".JPG", ".JPEG"}

# --- Performance ---
MAX_WORKERS = 8
