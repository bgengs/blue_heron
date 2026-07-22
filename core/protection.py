"""
Photo Theft Protection — "Stealth Mark" layers.
================================================

This module implements the protection layers applied to web-published JPGs:

  Layer 1  apply_micro_mark           Subtle tiled BG-glyph overlay
  Layer 2  embed_dct_watermark        Robust invisible DCT-domain ID
  Layer 3  compute_phash / compute_dhash  Perceptual hashes for registry

Layers 1+2 produce a final RGB image. Layer 3 fingerprints the FINAL image so
the registry matches what visitors actually see.

The DCT watermark uses Quantization Index Modulation (QIM) at a mid-frequency
coefficient (3,4) of each selected 8x8 luma block. Quantization step is large
enough (50.0) to survive JPEG re-compression down to ~q60, and pseudo-random
block selection (seeded by DCT_MASTER_KEY) makes the watermark hard to locate
without the key.

Implementation notes:
- No opencv/scipy dependencies — pure numpy DCT via precomputed 8x8 matrix.
- YCbCr conversion done manually (JPEG-style formula) to keep deps minimal.
- A 64-bit photo ID + 16-bit CRC = 80 bits total, each repeated 8 times for
  redundancy. Total ~640 blocks consumed, < 3% of a 1600x1067 image.
"""

import hashlib
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# --- DCT watermark ---
DCT_BLOCK = 8                          # JPEG-native block size
DCT_COEF_POS = (3, 4)                  # Mid-frequency position for QIM
DCT_QIM_STEP = 50.0                    # Quantization step (survives q60 JPEG)
DCT_REDUNDANCY = 8                     # Each bit embedded in N blocks
DCT_PAYLOAD_BITS = 64                  # Photo ID size
DCT_CRC_BITS = 16                      # CRC for validation
DCT_TOTAL_BITS = DCT_PAYLOAD_BITS + DCT_CRC_BITS  # 80
DCT_MASTER_KEY = 0xBE6E1EC0DEBEEF      # Seeds pseudo-random block picker

# --- Micro-mark (Layer 1) ---
MICRO_TILE_PX = 16                     # Glyph tile size (must be >= 8 to survive JPEG)
MICRO_SPACING_PX = 180                 # Distance between tiles
MICRO_OPACITY = 0.07                   # 7% — barely visible at viewing distance
MICRO_OFFSET_ROW = 90                  # Brick-pattern row offset

# --- Perceptual hash sizes ---
PHASH_REDUCE = 32                      # Reduce to 32x32, take 8x8 of DCT
PHASH_KEEP = 8
DHASH_W = 9                            # 9x8, compare adjacent columns -> 64 bits
DHASH_H = 8


# ---------------------------------------------------------------------------
# Precomputed DCT matrices (orthonormal DCT-II)
# ---------------------------------------------------------------------------

def _dct_matrix(n: int) -> np.ndarray:
    """Orthonormal DCT-II basis matrix of size n×n.

    For an n×n image block X, the 2D DCT is M @ X @ M.T, and the inverse is
    M.T @ X @ M. Both use the same matrix because M is orthonormal.
    """
    k = np.arange(n).reshape(-1, 1)
    i = np.arange(n).reshape(1, -1)
    m = np.cos(np.pi * k * (2 * i + 1) / (2 * n))
    m[0, :] *= 1.0 / np.sqrt(n)
    m[1:, :] *= np.sqrt(2.0 / n)
    return m


_DCT8 = _dct_matrix(DCT_BLOCK)
_DCT32 = _dct_matrix(PHASH_REDUCE)


def _dct2_8(block: np.ndarray) -> np.ndarray:
    return _DCT8 @ block @ _DCT8.T


def _idct2_8(block: np.ndarray) -> np.ndarray:
    return _DCT8.T @ block @ _DCT8


def _dct2_32(block: np.ndarray) -> np.ndarray:
    return _DCT32 @ block @ _DCT32.T


# ---------------------------------------------------------------------------
# YCbCr conversion (JPEG formula, integer math avoided for accuracy)
# ---------------------------------------------------------------------------

def _rgb_to_ycbcr(rgb: np.ndarray) -> np.ndarray:
    """RGB uint8 -> YCbCr float32. Shape preserved."""
    r = rgb[:, :, 0].astype(np.float32)
    g = rgb[:, :, 1].astype(np.float32)
    b = rgb[:, :, 2].astype(np.float32)
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = -0.168736 * r - 0.331264 * g + 0.5 * b + 128.0
    cr = 0.5 * r - 0.418688 * g - 0.081312 * b + 128.0
    return np.stack([y, cb, cr], axis=-1)


def _ycbcr_to_rgb(ycbcr: np.ndarray) -> np.ndarray:
    """YCbCr float32 -> RGB uint8. Values clipped to [0, 255]."""
    y = ycbcr[:, :, 0]
    cb = ycbcr[:, :, 1] - 128.0
    cr = ycbcr[:, :, 2] - 128.0
    r = y + 1.402 * cr
    g = y - 0.344136 * cb - 0.714136 * cr
    b = y + 1.772 * cb
    out = np.stack([r, g, b], axis=-1)
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Perceptual hashes (Layer 3)
# ---------------------------------------------------------------------------

def compute_phash(image: Image.Image) -> str:
    """64-bit DCT-based perceptual hash (16-char hex).

    Standard pHash:
      grayscale -> 32x32 -> DCT -> take top-left 8x8 (excluding DC) ->
      threshold at median -> 64 bits.
    """
    img = image.convert("L").resize((PHASH_REDUCE, PHASH_REDUCE), Image.LANCZOS)
    arr = np.asarray(img, dtype=np.float32)
    dct = _dct2_32(arr)
    low = dct[:PHASH_KEEP, :PHASH_KEEP].flatten()
    # Exclude DC (index 0) from median calculation
    median = float(np.median(low[1:]))
    bits = (low > median).astype(np.uint8)
    bits[0] = 0  # Force DC bit to 0 for consistency
    value = 0
    for i, b in enumerate(bits[:64]):
        if b:
            value |= 1 << (63 - i)
    return f"{value:016x}"


def compute_dhash(image: Image.Image) -> str:
    """64-bit difference hash (16-char hex).

    Compare each pixel to its right neighbor in a 9x8 grayscale image -> 64 bits.
    """
    img = image.convert("L").resize((DHASH_W, DHASH_H), Image.LANCZOS)
    arr = np.asarray(img, dtype=np.int16)
    diff = (arr[:, 1:] > arr[:, :-1]).flatten()
    value = 0
    for i, b in enumerate(diff):
        if b:
            value |= 1 << (63 - i)
    return f"{value:016x}"


def hamming_distance(hash_a: str, hash_b: str) -> int:
    """Bit-distance between two hex hashes — useful for fuzzy matching."""
    return bin(int(hash_a, 16) ^ int(hash_b, 16)).count("1")


# ---------------------------------------------------------------------------
# Photo ID derivation + CRC
# ---------------------------------------------------------------------------

def derive_photo_id(source_bytes: bytes) -> int:
    """First 64 bits of SHA-512(source_bytes) as an unsigned int."""
    return int.from_bytes(hashlib.sha512(source_bytes).digest()[:8], "big")


def _crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _id_to_bits(photo_id: int) -> List[int]:
    """64-bit ID -> 80-bit payload (ID + CRC16) as list of 0/1."""
    payload = photo_id.to_bytes(8, "big")
    crc = _crc16(payload).to_bytes(2, "big")
    raw = payload + crc
    bits: List[int] = []
    for byte in raw:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def _bits_to_id(bits: List[int]) -> Optional[int]:
    """80-bit list -> photo ID, or None if CRC fails."""
    if len(bits) != DCT_TOTAL_BITS:
        return None
    raw = bytearray()
    for i in range(0, DCT_TOTAL_BITS, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        raw.append(byte)
    payload = bytes(raw[:8])
    crc_recv = int.from_bytes(raw[8:10], "big")
    if crc_recv != _crc16(payload):
        return None
    return int.from_bytes(payload, "big")


# ---------------------------------------------------------------------------
# DCT robust watermark (Layer 2)
# ---------------------------------------------------------------------------

def _select_block_indices(num_needed: int, total_blocks: int) -> np.ndarray:
    """Deterministic pseudo-random unique-block selection."""
    rng = np.random.RandomState(DCT_MASTER_KEY & 0xFFFFFFFF)
    return rng.choice(total_blocks, size=num_needed, replace=False)


def embed_dct_watermark(image_rgb: np.ndarray, photo_id: int) -> np.ndarray:
    """Embed photo ID into image via QIM on mid-frequency DCT coefficients.

    Args:
        image_rgb: H x W x 3 uint8 RGB array.
        photo_id: 64-bit unsigned integer to encode.

    Returns:
        H x W x 3 uint8 RGB array with watermark embedded in Y channel.
    """
    ycbcr = _rgb_to_ycbcr(image_rgb)
    y = ycbcr[:, :, 0]
    h, w = y.shape

    # Pad to 8x8 boundary (cropped back at the end)
    pad_h = (DCT_BLOCK - h % DCT_BLOCK) % DCT_BLOCK
    pad_w = (DCT_BLOCK - w % DCT_BLOCK) % DCT_BLOCK
    if pad_h or pad_w:
        y = np.pad(y, ((0, pad_h), (0, pad_w)), mode="edge")
    hp, wp = y.shape
    blocks_w = wp // DCT_BLOCK
    blocks_h = hp // DCT_BLOCK
    total_blocks = blocks_h * blocks_w

    bits = _id_to_bits(photo_id)
    redundant = []
    for b in bits:
        redundant.extend([b] * DCT_REDUNDANCY)
    need = len(redundant)
    if need > total_blocks:
        raise ValueError(
            f"Image too small for watermark: needs {need} blocks, has {total_blocks}"
        )

    indices = _select_block_indices(need, total_blocks)
    cy, cx = DCT_COEF_POS

    for slot, block_idx in enumerate(indices):
        by, bx = divmod(int(block_idx), blocks_w)
        y0, x0 = by * DCT_BLOCK, bx * DCT_BLOCK
        block = y[y0:y0 + DCT_BLOCK, x0:x0 + DCT_BLOCK].astype(np.float32)
        dct = _dct2_8(block)
        coef = dct[cy, cx]
        n = int(round(coef / DCT_QIM_STEP))
        bit = redundant[slot]
        if (n % 2) != bit:
            # Flip parity by moving to the nearer ±1 neighbor
            if coef >= n * DCT_QIM_STEP:
                n += 1
            else:
                n -= 1
        dct[cy, cx] = n * DCT_QIM_STEP
        y[y0:y0 + DCT_BLOCK, x0:x0 + DCT_BLOCK] = _idct2_8(dct)

    y = y[:h, :w]
    ycbcr[:, :, 0] = np.clip(y, 0.0, 255.0)
    return _ycbcr_to_rgb(ycbcr)


def extract_dct_watermark(image_rgb: np.ndarray) -> Optional[int]:
    """Extract photo ID from a (possibly re-compressed) image.

    Returns the embedded photo ID, or None if the CRC fails (meaning either
    no watermark or it was destroyed beyond recovery).
    """
    ycbcr = _rgb_to_ycbcr(image_rgb)
    y = ycbcr[:, :, 0]
    h, w = y.shape

    pad_h = (DCT_BLOCK - h % DCT_BLOCK) % DCT_BLOCK
    pad_w = (DCT_BLOCK - w % DCT_BLOCK) % DCT_BLOCK
    if pad_h or pad_w:
        y = np.pad(y, ((0, pad_h), (0, pad_w)), mode="edge")
    hp, wp = y.shape
    blocks_w = wp // DCT_BLOCK
    blocks_h = hp // DCT_BLOCK
    total_blocks = blocks_h * blocks_w

    need = DCT_TOTAL_BITS * DCT_REDUNDANCY
    if need > total_blocks:
        return None

    indices = _select_block_indices(need, total_blocks)
    cy, cx = DCT_COEF_POS

    raw_bits: List[int] = []
    for block_idx in indices:
        by, bx = divmod(int(block_idx), blocks_w)
        y0, x0 = by * DCT_BLOCK, bx * DCT_BLOCK
        block = y[y0:y0 + DCT_BLOCK, x0:x0 + DCT_BLOCK].astype(np.float32)
        dct = _dct2_8(block)
        n = int(round(dct[cy, cx] / DCT_QIM_STEP))
        raw_bits.append(n & 1)

    # Majority-vote across redundant copies
    bits: List[int] = []
    for i in range(DCT_TOTAL_BITS):
        votes = raw_bits[i * DCT_REDUNDANCY:(i + 1) * DCT_REDUNDANCY]
        bits.append(1 if sum(votes) > DCT_REDUNDANCY // 2 else 0)

    return _bits_to_id(bits)


# ---------------------------------------------------------------------------
# Visible micro-mark (Layer 1)
# ---------------------------------------------------------------------------

def apply_micro_mark(
    image: Image.Image,
    glyph_rgba: Image.Image,
    tile_px: int = MICRO_TILE_PX,
    spacing: int = MICRO_SPACING_PX,
    opacity: float = MICRO_OPACITY,
    row_offset: int = MICRO_OFFSET_ROW,
) -> Image.Image:
    """Tile a small BG glyph across the image in an offset brick pattern.

    Produces a near-invisible repeating pattern at low opacity. Tile size is
    >= 8px so the pattern survives JPEG compression (smaller would be wiped
    by quantization of high-frequency DCT coefficients).

    Args:
        image: RGB PIL image to mark.
        glyph_rgba: RGBA glyph image (e.g., assets/bgg.png).
        tile_px: Glyph tile edge length, in pixels.
        spacing: Distance between tile origins.
        opacity: Tile opacity, 0.0–1.0.
        row_offset: Horizontal offset on odd rows (brick pattern).

    Returns:
        RGB PIL image with overlay applied.
    """
    base = image.convert("RGBA") if image.mode != "RGBA" else image.copy()

    glyph = glyph_rgba.resize((tile_px, tile_px), Image.LANCZOS).convert("RGBA")
    r, g, b, a = glyph.split()
    a = a.point(lambda v: int(v * opacity))
    glyph = Image.merge("RGBA", (r, g, b, a))

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    w, h = base.size
    rows = (h // spacing) + 2
    cols = (w // spacing) + 2
    for row in range(rows):
        y = row * spacing
        x_off = row_offset if row % 2 == 1 else 0
        for col in range(cols):
            x = col * spacing + x_off
            if -tile_px < x < w and -tile_px < y < h:
                overlay.paste(glyph, (x, y), glyph)

    composited = Image.alpha_composite(base, overlay)
    return composited.convert("RGB")


# ---------------------------------------------------------------------------
# High-level orchestration
# ---------------------------------------------------------------------------

@dataclass
class ProtectionMetadata:
    """Per-photo protection metadata. Persisted in registry.json."""

    photo_id: int = 0
    photo_id_hex: str = ""
    phash: str = ""
    dhash: str = ""
    stego_id: str = ""

    def to_dict(self) -> dict:
        return {
            "photo_id_hex": self.photo_id_hex,
            "phash": self.phash,
            "dhash": self.dhash,
            "stego_id": self.stego_id,
        }


def apply_web_protection(
    image: Image.Image,
    glyph_rgba: Image.Image,
    source_bytes: bytes,
    stego_id: str,
) -> Tuple[Image.Image, ProtectionMetadata]:
    """Apply Layer 1 (micro-mark) + Layer 2 (DCT watermark) and compute hashes.

    The order is intentional: visible micro-mark FIRST (adds spatial-domain
    structure), then DCT watermark (operates on luma DCT coefficients of the
    already-marked image). They are orthogonal — neither destroys the other.

    Hashes are computed on the FINAL image so the registry matches what the
    site actually serves.

    Args:
        image: RGB PIL image (already resized to web target).
        glyph_rgba: BG logo PNG with alpha.
        source_bytes: Bytes of the original source file (for ID derivation).
        stego_id: Full stego-identifier string from watermark.py.

    Returns:
        Tuple of (protected RGB image, ProtectionMetadata).
    """
    # Layer 1: tiled micro-mark
    marked = apply_micro_mark(image, glyph_rgba)

    # Layer 2: invisible DCT watermark in luma
    photo_id = derive_photo_id(source_bytes)
    arr = np.asarray(marked, dtype=np.uint8)
    arr_watermarked = embed_dct_watermark(arr, photo_id)
    final = Image.fromarray(arr_watermarked, "RGB")

    # Layer 3: fingerprint final image
    phash = compute_phash(final)
    dhash = compute_dhash(final)

    return final, ProtectionMetadata(
        photo_id=photo_id,
        photo_id_hex=f"{photo_id:016x}",
        phash=phash,
        dhash=dhash,
        stego_id=stego_id,
    )
