"""Owner-run export of bot photos for labelling, before the 30-day delete (research R10).

Writes, outside the repo: images/<name>.jpg, a Label Studio tasks.json with the detector's boxes as
pre-annotations, and corrections.json. Needs `gcloud auth application-default login` once.
Usage: python scripts/export_dataset.py --out C:/pantry-vision-data/export [--all]
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def label_studio_task(image_name: str, width: int, height: int, detections: list[dict]) -> dict:
    """One Label Studio task with the detector's boxes as a prediction, in percent coordinates."""
    results = []
    for i, d in enumerate(detections):
        x1, y1, x2, y2 = d["box"]
        results.append(
            {
                "id": f"d{i}",
                "from_name": "label",
                "to_name": "image",
                "type": "rectanglelabels",
                "original_width": width,
                "original_height": height,
                "value": {
                    "x": 100 * x1 / width,
                    "y": 100 * y1 / height,
                    "width": 100 * (x2 - x1) / width,
                    "height": 100 * (y2 - y1) / height,
                    "rectanglelabels": [d["key"]],
                },
                "score": d["score"],
            }
        )
    return {
        "data": {"image": f"/data/local-files/?d=images/{image_name}"},
        "predictions": [{"model_version": "detector", "result": results}],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True, help="a folder outside the repo")
    parser.add_argument("--all", action="store_true", help="every stored photo, not only corrected ones")
    args = parser.parse_args()
    if ROOT in args.out.resolve().parents or args.out.resolve() == ROOT:
        sys.exit("refusing to export inside the repository: photos are never committed")

    from google.cloud import firestore, storage
    from PIL import Image

    env = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines() if "=" in line)
    project = env.get("GOOGLE_CLOUD_PROJECT") or os.environ["GOOGLE_CLOUD_PROJECT"]
    bucket = storage.Client(project=project).bucket(f"{project}-pantry-photos")
    db = firestore.Client(project=project)

    corrections = [c.to_dict() for c in db.collection("pantry_corrections").stream()]
    wanted = {c["snapshot_id"] for c in corrections if c.get("snapshot_id")}
    snaps = [s.to_dict() for s in db.collection("pantry_snapshots").stream()]
    if not args.all:
        snaps = [s for s in snaps if s["id"] in wanted]

    images_dir = args.out / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    tasks, exported, gone = [], 0, 0
    for snap in snaps:
        for n, photo in enumerate(snap.get("photos", [])):
            name = f"{snap['id']}_{n}.jpg"
            target = images_dir / name
            if not target.exists():
                blob = bucket.blob(photo["blob_path"])
                if not blob.exists():
                    gone += 1  # already past the 30-day delete
                    continue
                blob.download_to_filename(target)
                exported += 1
            with Image.open(target) as img:
                width, height = img.size
            tasks.append(label_studio_task(name, width, height, photo.get("detections", [])))

    (args.out / "tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")
    keep = ("snapshot_id", "key", "kind", "old_count", "new_count")
    rows = [{k: c.get(k) for k in keep} for c in corrections]
    (args.out / "corrections.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"new photos: {exported}, tasks: {len(tasks)}, already deleted: {gone}, out: {args.out}")


if __name__ == "__main__":
    main()
