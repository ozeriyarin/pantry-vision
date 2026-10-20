"""Run the detector on local photos: `python -m pantry.detection.smoke photo.jpg [...]`. No network."""

import argparse
import time
from pathlib import Path

from pantry.config import ROOT, load_settings
from pantry.detection.images import open_image
from pantry.detection.onnx_detector import OnnxDetector
from pantry.detection.quality import check_quality


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("photos", nargs="+", type=Path)
    parser.add_argument("--model", type=Path, default=ROOT / "models/yolo-world-s-pantry.onnx")
    args = parser.parse_args()

    settings = load_settings({})
    detector = OnnxDetector(args.model, settings.min_score, settings.agnostic_iou)
    for path in args.photos:
        data = path.read_bytes()
        q = check_quality(
            open_image(data), settings.quality.min_luminance, settings.quality.min_laplacian_var
        )
        start = time.perf_counter()
        found = detector.detect(data)
        ms = (time.perf_counter() - start) * 1000
        print(f"{path.name}: quality {'ok' if q.ok else q.reason}, {len(found)} boxes, {ms:.0f} ms")
        for d in found:
            band = "certain" if d.score >= settings.uncertain_score else "uncertain"
            print(f"  {d.key:<20} {d.score:.2f} {band}")


if __name__ == "__main__":
    main()
