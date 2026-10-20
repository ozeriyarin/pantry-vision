"""Second recognition step on uncertain crops only, under a monthly cap (FR-004, Principle II)."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace

from PIL import Image

from pantry.config import Crop
from pantry.config import Fallback as FallbackSettings
from pantry.detection.images import to_jpeg
from pantry.domain.models import Detection
from pantry.ports import Clock, Store, Verifier


class VerifyFailed(Exception):
    """Billed call with no usable answer, such as a refusal."""

    def __init__(self, reason: str, cost_usd: float):
        super().__init__(reason)
        self.cost_usd = cost_usd


@dataclass(frozen=True)
class FallbackOutcome:
    detections: list[Detection]  # same order as input; .fallback set when verified
    calls: int
    skipped: int
    cost_usd: float


def crop(image: Image.Image, box: tuple[float, float, float, float], pad: float, max_side: int) -> bytes:
    x1, y1, x2, y2 = box
    dx, dy = (x2 - x1) * pad, (y2 - y1) * pad
    region = (
        max(0, int(x1 - dx)),
        max(0, int(y1 - dy)),
        min(image.width, int(x2 + dx) + 1),
        min(image.height, int(y2 + dy) + 1),
    )
    piece = image.crop(region)
    piece.thumbnail((max_side, max_side))
    return to_jpeg(piece)


class Fallback:
    def __init__(
        self,
        verifier: Verifier,
        store: Store,
        clock: Clock,
        settings: FallbackSettings,
        crop_settings: Crop,
        max_workers: int = 4,
    ):
        self._verifier, self._store, self._clock = verifier, store, clock
        self._settings, self._crop = settings, crop_settings
        self._max_workers = max_workers

    def check(self, image: Image.Image, detections: list[Detection], keys: list[str]) -> FallbackOutcome:
        if not detections:
            return FallbackOutcome([], 0, 0, 0.0)
        month = self._clock.now().strftime("%Y-%m")
        cap = self._settings.cap_usd
        budget = self._store.get_budget(month, cap)
        if budget.spent_usd >= cap:
            return FallbackOutcome(list(detections), 0, len(detections), 0.0)

        # Bound spend per photo: the highest-scoring crops, at most what the remaining budget covers.
        allowed = int((cap - budget.spent_usd) / self._settings.est_cost_per_call + 1e-6)
        limit = min(self._settings.max_calls_per_photo, max(allowed, 1))
        order = sorted(range(len(detections)), key=lambda i: -detections[i].score)
        chosen = set(order[:limit])
        picked = [detections[i] for i in range(len(detections)) if i in chosen]
        crops = [crop(image, d.box, self._crop.pad, self._crop.max_side) for d in picked]
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = [pool.submit(self._verifier.verify, c, keys) for c in crops]
            answers = []
            for f in futures:
                try:
                    answers.append(f.result())
                except Exception as exc:  # noqa: BLE001  any failure leaves the item uncertain
                    answers.append(exc)

        answer_for = dict(zip((i for i in range(len(detections)) if i in chosen), answers, strict=True))
        out, calls, skipped, cost = [], 0, 0, 0.0
        for i, det in enumerate(detections):
            if i not in answer_for:
                skipped += 1
                out.append(det)
                continue
            answer = answer_for[i]
            calls += 1
            if isinstance(answer, Exception):
                skipped += 1
                cost += getattr(answer, "cost_usd", 0.0)
                out.append(det)
            else:
                cost += answer.cost_usd
                out.append(replace(det, fallback=answer))
        if cost:
            self._store.add_spend(month, cost, cap)
        return FallbackOutcome(out, calls, skipped, cost)
