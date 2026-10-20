"""Run the ONNX detector over a labelled set and write the README table (quickstart step 3). Offline only.

Data layout (Label Studio "YOLO" export): <data>/images/*.jpg, <data>/labels/*.txt, <data>/classes.txt.
Class names must be item keys from config/items.yaml. Photos stay outside the repo.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.metrics import Pred, Truth, evaluate, markdown  # noqa: E402
from pantry.config import load_settings  # noqa: E402
from pantry.detection.images import open_image  # noqa: E402
from pantry.detection.onnx_detector import OnnxDetector  # noqa: E402


def read_labels(path: Path, classes: list[str], width: int, height: int) -> list[Truth]:
    truths = []
    if not path.exists():
        return truths
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        c, cx, cy, w, h = int(parts[0]), *map(float, parts[1:])
        box = ((cx - w / 2) * width, (cy - h / 2) * height, (cx + w / 2) * width, (cy + h / 2) * height)
        truths.append(Truth(classes[c], box))
    return truths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=ROOT / "models/yolo-world-s-pantry.onnx")
    parser.add_argument("--min-score", type=float, default=None, help="default: settings min_score")
    parser.add_argument("--out", type=Path, default=ROOT / "eval/out")
    args = parser.parse_args()

    settings = load_settings({})
    min_score = settings.min_score if args.min_score is None else args.min_score
    detector = OnnxDetector(args.model, min_score, settings.agnostic_iou)
    classes = (args.data / "classes.txt").read_text(encoding="utf-8").split()
    unknown = sorted(set(classes) - set(detector.classes))
    if unknown:
        print(f"note: label classes the model cannot predict: {', '.join(unknown)}")

    images = []
    for photo in sorted((args.data / "images").glob("*")):
        if photo.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        img = open_image(photo.read_bytes())
        truths = read_labels(args.data / "labels" / f"{photo.stem}.txt", classes, img.width, img.height)
        preds = [Pred(d.key, d.box, d.score) for d in detector.detect(photo.read_bytes())]
        images.append((truths, preds))

    report = evaluate(images)
    table = markdown(report, f"{detector.model_name} (min score {min_score})")
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / f"{args.model.stem}-{date.today():%Y%m%d}.md"
    out.write_text(table + "\n", encoding="utf-8")
    print(table)
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    main()
