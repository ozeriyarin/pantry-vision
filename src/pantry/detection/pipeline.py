"""Quality check, detect, verify the uncertain band, count per item (FR-001, FR-003, FR-004)."""

from dataclasses import dataclass, field
from typing import Literal

from pantry.config import Settings
from pantry.detection.fallback import Fallback
from pantry.detection.images import open_image
from pantry.detection.quality import check_quality
from pantry.domain.models import Detection, SnapshotItem
from pantry.ports import Detector


@dataclass
class PipelineResult:
    status: Literal["ok", "unclear", "empty"]
    items: dict[str, SnapshotItem] = field(default_factory=dict)
    detections: list[Detection] = field(default_factory=list)
    fallback_calls: int = 0
    skipped: int = 0
    cost_usd: float = 0.0


def _add(items: dict[str, SnapshotItem], key: str, count: int, score: float, uncertain: bool, source) -> None:
    current = items.get(key)
    if current is None:
        items[key] = SnapshotItem(count, score, uncertain, source)
        return
    current.count += count
    current.score = max(current.score, score)
    current.uncertain = current.uncertain or uncertain
    if source == "fallback":
        current.source = "fallback"


class Pipeline:
    def __init__(self, detector: Detector, fallback: Fallback, settings: Settings):
        self._detector, self._fallback, self._settings = detector, fallback, settings

    def run(self, image_bytes: bytes, keys: list[str]) -> PipelineResult:
        image = open_image(image_bytes)
        quality = check_quality(
            image, self._settings.quality.min_luminance, self._settings.quality.min_laplacian_var
        )
        if not quality.ok:
            return PipelineResult("unclear")

        found = [d for d in self._detector.detect(image_bytes) if d.score >= self._settings.min_score]
        certain = [d for d in found if d.score >= self._settings.uncertain_score]
        band = [d for d in found if d.score < self._settings.uncertain_score]
        outcome = self._fallback.check(image, band, keys)

        items: dict[str, SnapshotItem] = {}
        for d in certain:
            _add(items, d.key, 1, d.score, False, "detector")
        for d in outcome.detections:
            if d.fallback is None:
                _add(items, d.key, 1, d.score, True, "detector")
            elif d.fallback.item != "none":
                _add(items, d.fallback.item, d.fallback.count, d.score, False, "fallback")

        return PipelineResult(
            "ok" if items else "empty",
            items,
            certain + outcome.detections,
            outcome.calls,
            outcome.skipped,
            outcome.cost_usd,
        )
