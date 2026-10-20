"""Detection metrics for the README table (Principle III): mAP@0.5, per-item P and R, count accuracy."""

from collections import Counter
from dataclasses import dataclass

Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class Truth:
    key: str
    box: Box


@dataclass(frozen=True)
class Pred:
    key: str
    box: Box
    score: float


def iou(a: Box, b: Box) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _match(truths: list[Truth], preds: list[Pred], key: str, thr: float) -> list[tuple[float, bool]]:
    """Greedy by score: each prediction of `key` is a true positive if it takes an unmatched truth."""
    gts = [t.box for t in truths if t.key == key]
    used = [False] * len(gts)
    out = []
    for p in sorted((p for p in preds if p.key == key), key=lambda p: -p.score):
        best, best_iou = -1, thr
        for i, g in enumerate(gts):
            v = iou(p.box, g)
            if not used[i] and v >= best_iou:
                best, best_iou = i, v
        if best >= 0:
            used[best] = True
        out.append((p.score, best >= 0))
    return out


def average_precision(hits: list[tuple[float, bool]], n_truth: int) -> float:
    """All-point interpolated AP over (score, is_true_positive) pairs."""
    if n_truth == 0:
        return 0.0
    hits = sorted(hits, key=lambda h: -h[0])
    tp = fp = 0
    points = []
    for _, ok in hits:
        tp, fp = tp + ok, fp + (not ok)
        points.append((tp / n_truth, tp / (tp + fp)))
    ap, prev_recall = 0.0, 0.0
    for i, (recall, _) in enumerate(points):
        best_precision = max(p for _, p in points[i:])
        ap += (recall - prev_recall) * best_precision
        prev_recall = recall
    return ap


@dataclass(frozen=True)
class ItemScore:
    key: str
    truths: int
    precision: float
    recall: float
    ap50: float


@dataclass(frozen=True)
class Report:
    map50: float
    count_accuracy: float
    items: list[ItemScore]
    images: int


def evaluate(images: list[tuple[list[Truth], list[Pred]]], thr: float = 0.5) -> Report:
    keys = sorted({t.key for truths, _ in images for t in truths})
    items = []
    for key in keys:
        hits, n_truth = [], 0
        for truths, preds in images:
            n_truth += sum(1 for t in truths if t.key == key)
            hits += _match(truths, preds, key, thr)
        tp = sum(ok for _, ok in hits)
        precision = tp / len(hits) if hits else 0.0
        recall = tp / n_truth if n_truth else 0.0
        items.append(ItemScore(key, n_truth, precision, recall, average_precision(hits, n_truth)))

    # Count accuracy: share of (photo, item) occurrences whose predicted count equals the label.
    occurrences = correct = 0
    for truths, preds in images:
        want, got = Counter(t.key for t in truths), Counter(p.key for p in preds)
        for key, n in want.items():
            occurrences += 1
            correct += got[key] == n
    count_accuracy = correct / occurrences if occurrences else 0.0
    map50 = sum(i.ap50 for i in items) / len(items) if items else 0.0
    return Report(map50, count_accuracy, items, len(images))


def markdown(report: Report, model: str) -> str:
    lines = [
        f"**{model}**: {report.images} photos, mAP@0.5 {report.map50:.3f}, "
        f"count accuracy {report.count_accuracy:.1%}",
        "",
        "| Item | Labels | Precision | Recall | AP@0.5 |",
        "|------|-------:|----------:|-------:|-------:|",
    ]
    for i in sorted(report.items, key=lambda i: -i.truths):
        lines.append(f"| {i.key} | {i.truths} | {i.precision:.2f} | {i.recall:.2f} | {i.ap50:.2f} |")
    return "\n".join(lines)
