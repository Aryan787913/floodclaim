"""Image prep: strip EXIF/location, resize, and perceptual hashing for duplicates."""
import hashlib
import io
from pathlib import Path

from PIL import Image, ImageOps

MAX_SIDE = 1280


def clean_image(raw: bytes) -> bytes:
    """Return a resized JPEG with all metadata (EXIF, GPS) removed."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)  # keep correct orientation before dropping EXIF
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    # Pillow writes no EXIF unless we pass exif=..., so metadata is dropped here
    img.save(out, format="JPEG", quality=90)
    return out.getvalue()


def clean_file(src: Path, dst: Path) -> bytes:
    data = clean_image(src.read_bytes())
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    return data


def dhash(raw: bytes, size: int = 8) -> int:
    """64-bit difference hash. Near-identical photos (re-saved, resized) give close hashes."""
    img = Image.open(io.BytesIO(raw)).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(img.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            left = px[row * (size + 1) + col]
            right = px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
