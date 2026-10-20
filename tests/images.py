"""Small generated JPEGs: noisy ones pass the quality check, dark ones fail it."""

import io

import numpy as np
from PIL import Image


def jpeg(seed: int = 0, size: tuple[int, int] = (640, 480), dark: bool = False, flat: bool = False) -> bytes:
    if dark:
        pixels = np.full((size[1], size[0], 3), 8, dtype=np.uint8)
    elif flat:
        pixels = np.full((size[1], size[0], 3), 128, dtype=np.uint8)
    else:
        pixels = np.random.default_rng(seed).integers(40, 255, (size[1], size[0], 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(pixels).save(buf, format="JPEG", quality=90)
    return buf.getvalue()
