"""Image decoding and resizing shared by the detector, quality check and crops."""

import io

import numpy as np
from PIL import Image, ImageOps


def open_image(data: bytes) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")


def letterbox(image: Image.Image, size: int) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize keeping aspect ratio and pad to a size x size square with gray 114, centered."""
    scale = size / max(image.size)
    w, h = round(image.width * scale), round(image.height * scale)
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    pad = ((size - w) // 2, (size - h) // 2)
    canvas.paste(image.resize((w, h), Image.BILINEAR), pad)
    return np.asarray(canvas), scale, pad


def to_jpeg(image: Image.Image, quality: int = 85) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
