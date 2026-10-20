"""YOLO-World exported to ONNX with baked classes, run on CPU (research R1)."""

import json
from pathlib import Path

import numpy as np

from pantry.detection.images import letterbox, open_image
from pantry.domain.models import Detection


def nms(boxes: np.ndarray, scores: np.ndarray, iou: float) -> list[int]:
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        i = order[0]
        keep.append(int(i))
        x1 = np.maximum(boxes[i, 0], boxes[order[1:], 0])
        y1 = np.maximum(boxes[i, 1], boxes[order[1:], 1])
        x2 = np.minimum(boxes[i, 2], boxes[order[1:], 2])
        y2 = np.minimum(boxes[i, 3], boxes[order[1:], 3])
        inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_o = (boxes[order[1:], 2] - boxes[order[1:], 0]) * (boxes[order[1:], 3] - boxes[order[1:], 1])
        order = order[1:][inter / (area_i + area_o - inter + 1e-9) < iou]
    return keep


def decode(
    output: np.ndarray,
    classes: list[str],
    scale: float,
    pad: tuple[int, int],
    size: tuple[int, int],
    min_score: float,
    iou: float = 0.7,
    agnostic_iou: float | None = None,
) -> list[Detection]:
    """output: (1, 4 + n_classes, anchors) with cx, cy, w, h in letterbox pixels and class scores."""
    preds = output[0].T
    cls_scores = preds[:, 4:]
    cls = cls_scores.argmax(axis=1)
    score = cls_scores[np.arange(len(cls)), cls]
    mask = score >= min_score
    if not mask.any():
        return []
    xywh, cls, score = preds[mask, :4], cls[mask], score[mask]
    boxes = np.empty_like(xywh)
    boxes[:, 0] = (xywh[:, 0] - xywh[:, 2] / 2 - pad[0]) / scale
    boxes[:, 1] = (xywh[:, 1] - xywh[:, 3] / 2 - pad[1]) / scale
    boxes[:, 2] = (xywh[:, 0] + xywh[:, 2] / 2 - pad[0]) / scale
    boxes[:, 3] = (xywh[:, 1] + xywh[:, 3] / 2 - pad[1]) / scale
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, size[0])
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, size[1])
    found: list[Detection] = []
    for c in np.unique(cls):
        idx = np.flatnonzero(cls == c)
        for k in nms(boxes[idx], score[idx], iou):
            j = idx[k]
            found.append(Detection(classes[int(c)], tuple(float(v) for v in boxes[j]), float(score[j])))
    found.sort(key=lambda d: -d.score)
    if agnostic_iou is not None and len(found) > 1:
        # One object, one label: zero-shot often names the same jar as jam, mustard and spread.
        keep = nms(np.array([d.box for d in found]), np.array([d.score for d in found]), agnostic_iou)
        found = [found[i] for i in sorted(keep)]
    return found


class OnnxDetector:
    def __init__(self, onnx_path: Path, min_score: float, agnostic_iou: float | None = None):
        import onnxruntime as ort

        meta = json.loads(onnx_path.with_suffix(".json").read_text(encoding="utf-8"))
        self.classes: list[str] = meta["classes"]
        self.imgsz: int = meta["imgsz"]
        self.model_name = f"{onnx_path.name}@{meta['sha256'][:12]}"
        self._min_score = min_score
        self._agnostic_iou = agnostic_iou
        self._session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        self._input = self._session.get_inputs()[0].name

    def detect(self, image: bytes) -> list[Detection]:
        img = open_image(image)
        pixels, scale, pad = letterbox(img, self.imgsz)
        tensor = (pixels.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
        output = self._session.run(None, {self._input: tensor})[0]
        return decode(
            output, self.classes, scale, pad, img.size, self._min_score, agnostic_iou=self._agnostic_iou
        )
