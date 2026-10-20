"""Compare the baked .pt with its ONNX export on spike photos (research R1). Prints counts only."""

import argparse
import json
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def square(photo: Path, size: int = 640):
    # Same 640x640 letterbox for both models, so only the export differs.
    import numpy as np
    from PIL import Image

    img = Image.open(photo).convert("RGB")
    scale = size / max(img.size)
    img = img.resize((round(img.width * scale), round(img.height * scale)))
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return np.asarray(canvas)[:, :, ::-1].copy()


def run(model, photo: Path, conf: float):
    start = time.perf_counter()
    result = model.predict(square(photo), conf=conf, imgsz=640, verbose=False)[0]
    ms = (time.perf_counter() - start) * 1000
    names = result.names
    classes = [names[int(c)] for c in result.boxes.cls.tolist()]
    return Counter(classes), result.boxes.conf.tolist(), ms


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("photos", type=Path, help="folder of spike photos, outside the repo")
    parser.add_argument("--name", default="yolo-world-s-pantry")
    parser.add_argument("--conf", type=float, default=0.10)
    args = parser.parse_args()

    from ultralytics import YOLO

    models_dir = ROOT / "models"
    keys = json.loads((models_dir / f"{args.name}.json").read_text(encoding="utf-8"))["classes"]
    pt = YOLO(str(models_dir / f"{args.name}.pt"))
    onnx = YOLO(str(models_dir / f"{args.name}.onnx"), task="detect")

    photos = sorted(p for p in args.photos.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    total_pt, total_onnx, max_delta, onnx_ms = Counter(), Counter(), 0.0, []
    for i, photo in enumerate(photos, 1):
        c_pt, s_pt, _ = run(pt, photo, args.conf)
        c_onnx, s_onnx, ms = run(onnx, photo, args.conf)
        onnx_ms.append(ms)
        total_pt += c_pt
        total_onnx += c_onnx
        if s_pt and s_onnx:
            max_delta = max(max_delta, abs(max(s_pt) - max(s_onnx)))
        same = "same" if c_pt == c_onnx else "DIFF"
        print(f"photo {i}: pt {sum(c_pt.values())} boxes, onnx {sum(c_onnx.values())} boxes, classes {same}")

    def label(name):
        return keys[int(name)] if str(name).isdigit() else name

    print(f"\nboxes total: pt {sum(total_pt.values())}, onnx {sum(total_onnx.values())}")
    print(f"max top-score delta: {max_delta:.3f}")
    print(f"onnx latency ms (warm): {sorted(onnx_ms)[len(onnx_ms) // 2]:.0f} median")
    print("onnx counts by class:", {label(k): v for k, v in total_onnx.most_common()})


if __name__ == "__main__":
    main()
