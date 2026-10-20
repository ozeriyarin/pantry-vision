"""Bake the item prompts into YOLO-World and export it to ONNX (research R1). Offline only."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_items(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["items"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", default="yolov8s-worldv2.pt")
    parser.add_argument("--items", type=Path, default=ROOT / "config/items.yaml")
    parser.add_argument("--out", type=Path, default=ROOT / "models")
    parser.add_argument("--name", default="yolo-world-s-pantry")
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()

    from ultralytics import YOLO, YOLOWorld

    items = load_items(args.items)
    args.out.mkdir(parents=True, exist_ok=True)
    model = YOLOWorld(str(args.out / args.weights))
    model.set_classes([i["prompt"] for i in items])
    custom_pt = args.out / f"{args.name}.pt"
    model.save(str(custom_pt))

    exported = Path(YOLO(str(custom_pt)).export(format="onnx", imgsz=args.imgsz, simplify=True))
    onnx_path = args.out / f"{args.name}.onnx"
    if exported.resolve() != onnx_path.resolve():
        shutil.move(exported, onnx_path)

    sidecar = {
        "model": onnx_path.name,
        "sha256": sha256(onnx_path),
        "source_weights": args.weights,
        "imgsz": args.imgsz,
        "classes": [i["key"] for i in items],
        "prompts": [i["prompt"] for i in items],
    }
    (args.out / f"{args.name}.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(f"exported {onnx_path.name} ({onnx_path.stat().st_size / 1e6:.1f} MB), {len(items)} classes")


if __name__ == "__main__":
    main()
