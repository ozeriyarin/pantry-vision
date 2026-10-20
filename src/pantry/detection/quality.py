"""Dark or blurry photo check before detection (edge case: retake)."""

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class QualityResult:
    ok: bool
    reason: str | None
    luminance: float
    sharpness: float


def check_quality(image: Image.Image, min_luminance: float, min_laplacian_var: float) -> QualityResult:
    gray = image.convert("L")
    gray.thumbnail((512, 512))
    g = np.asarray(gray, dtype=np.float32)
    luminance = float(g.mean())
    lap = g[1:-1, :-2] + g[1:-1, 2:] + g[:-2, 1:-1] + g[2:, 1:-1] - 4 * g[1:-1, 1:-1]
    sharpness = float(lap.var())
    if luminance < min_luminance:
        return QualityResult(False, "dark", luminance, sharpness)
    if sharpness < min_laplacian_var:
        return QualityResult(False, "blurry", luminance, sharpness)
    return QualityResult(True, None, luminance, sharpness)
