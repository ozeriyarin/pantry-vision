# Pantry Vision

A Hebrew Telegram bot that turns photos of the fridge, freezer and pantry into an inventory. Send a photo,
get back the items with counts, fix mistakes with a short reply, ask "מה יש לי?", and get a 07:30 message
listing what ran out. Built for one household, runs on Google Cloud for well under 10 USD a month.

The point of the project: a non-LLM AI skill (computer vision with a real eval) and a second spec-driven
framework, [GitHub spec-kit](https://github.com/github/spec-kit). The spec, plan, research notes, data model,
contracts and task list are in [`specs/001-pantry-photo-inventory/`](specs/001-pantry-photo-inventory/); the
project rules are in the [constitution](.specify/memory/constitution.md).

## How it works

```text
Telegram photo ──> Cloud Run (FastAPI webhook, secret header, allow-listed chat)
                     │
                     ├─ quality check (dark or blurry: ask for a retake)
                     ├─ YOLO-World zero-shot detector, ONNX on CPU, 39 item prompts baked in
                     │    one label per object, score >= 0.20
                     ├─ uncertain boxes (0.20-0.35): crop -> Claude Haiku 5.5, max 8 per photo, monthly cap
                     ├─ photo session: photos within 5 min merge by highest count; "סיימתי" = full view
                     └─ Firestore: inventory, snapshots, corrections (training labels), run records
Cloud Scheduler 07:30 ──(OIDC)──> /tasks/morning ──> "נגמרו מאתמול: ..." or "הכול בסדר"
```

- **Cheap model first.** The local detector handles every photo; Claude sees only small crops the detector is
  unsure about, never the whole photo, and every call's cost is recorded.
- **Corrections are data.** "ביצים 4", "אין חלב", "להוסיף חומוס", a multi-line list, "מקפיא: גלידה 2", or the
  ✓/✗ buttons update the inventory at once and are stored with the photo as labels for fine-tuning.
- **Unknown names** get one question per message; names close to a known item get "התכוונת ל...?".

## Talking to the bot

| You send | The bot does |
|----------|--------------|
| a photo, caption מקרר / מקפיא / מזווה (none = fridge) | lists items with counts, "?" plus ✓/✗ on uncertain ones |
| "סיימתי" | closes the photo round as a full view; items not seen go to 0 |
| "ביצים 4", "אין חלב", "להוסיף חומוס 2" | updates the item, replies "עודכן" |
| several lines or commas, optionally "מקפיא:" | applies each line, asks once about unknown names |
| "מה יש לי", "מה יש במקפיא", "יש ביצים?" | answers from the inventory |

## Accuracy

Measured with [`eval/run_eval.py`](eval/run_eval.py) on the owner's labelled photos: mAP@0.5, per-item
precision and recall, and count accuracy (share of photo-item pairs whose predicted count equals the label).

| Model | Photos | mAP@0.5 | Count accuracy |
|-------|-------:|--------:|---------------:|
| YOLO-World s, zero-shot (baseline) | pending | pending | pending |
| YOLO11 s, fine-tuned on owner photos | pending | pending | target 80% |

The labelled set is being collected. Early signal from the first real photo: the zero-shot detector over-detects
generic bottles and jars, which is why one-label-per-object, a 0.20 score floor and narrower prompts were added.

## Cost

| Item | Monthly |
|------|--------:|
| Cloud Run, Firestore, Cloud Scheduler, Secret Manager, Cloud Build | 0 (free tier) |
| Cloud Storage (photos, 30-day delete) and Artifact Registry (2 images kept) | about 0.10 USD |
| Claude Haiku on uncertain crops | about 0.0007 USD per photo, app cap 1 USD |
| **Expected total** | **under 1 USD** |

Hard limits: one Cloud Run instance at most, scale to zero, the Anthropic key's own spending limit, and a GCP
budget alert on resources labelled `app=pantry-vision`.

## Privacy

Photos of a home are private. They live in a private bucket that deletes them after 30 days, are never logged
or committed, and only cropped regions reach Claude. Run records hold counts, scores, cost and latency, never
image data. Logs carry ids and error types, not captions or message text, and a test enforces that. The bot
answers one allow-listed chat. Training photos are exported by the owner to a private workspace
(constitution v1.1.0).

## Run it

```bash
python -m uv sync --group dev
python -m uv run pytest
python -m uv run ruff check
```

Detector on local photos, and the eval:

```bash
python -m uv run python -m pantry.detection.smoke path/to/photo.jpg
python -m uv run python eval/run_eval.py --data path/to/labelled
```

Deploy (pwsh 7, gcloud signed in, values in a gitignored `.env`, see `.env.example`):

```bash
pwsh -File scripts/deploy.ps1 -Step all
```

## Labelling and fine-tuning

1. `python -m uv run python scripts/export_dataset.py --out C:/pantry-vision-data/export` downloads corrected
   bot photos before the 30-day delete, with the detector's boxes as pre-labels.
2. Label in [Label Studio](https://labelstud.io) running locally; `python scripts/label_config.py` prints the
   labelling config with every item key. Export in YOLO format.
3. Train with [`training/finetune.ipynb`](training/finetune.ipynb) on a free Colab GPU, evaluate, and ship only
   with before and after numbers in the table above.

## Licence

AGPL-3.0, because the detector tooling (Ultralytics) is AGPL-3.0.
