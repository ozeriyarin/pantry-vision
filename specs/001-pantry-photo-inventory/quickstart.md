# Quickstart: validate spec 001

How to prove the feature works. Interfaces: [contracts/](contracts/). Entities: [data-model.md](data-model.md).

## Prerequisites

- Python 3.11 and `uv`.
- For the cloud checks: pwsh 7, Cloud SDK on PATH, access to project `<GOOGLE_CLOUD_PROJECT in .env>`,
  secrets `PANTRY_TELEGRAM_BOT_TOKEN`, `PANTRY_TELEGRAM_WEBHOOK_SECRET`, `PANTRY_ANTHROPIC_API_KEY` in
  Secret Manager (owner creates the bot and the capped key).
- The ONNX model at `gs://<bucket>/models/` (produced by `training/export_onnx.py`).

## 1. Offline gate (no keys, no network)

```bash
uv sync --group dev
uv run pytest
uv run ruff check
```

Expected: all tests pass. Every acceptance scenario has a test whose docstring quotes it (Principle VI);
`tests/integration/` drives the FastAPI app with fake Telegram, store, blob, detector and fallback.

## 2. Detector smoke (local, needs the ONNX file)

```bash
uv run python -m pantry.detection.smoke path/to/fridge.jpg
```

Expected: a list of items with scores, under 2 s on a laptop CPU.

## 3. Eval (offline, owner's labelled set)

```bash
uv run python eval/run_eval.py --data path/to/labelled --model models/yolo-world-s.onnx
```

Expected: a Markdown table with mAP@0.5, per-item precision and recall, count accuracy. Zero-shot has no
pass mark; the fine-tuned model must reach 80 percent count accuracy (SC-002).

## 4. Deploy

```bash
pwsh -File scripts/deploy.ps1 -Step all
```

Expected: image built by the dedicated build account, service `pantry-bot` live with min 0, max 1,
concurrency 1; webhook registered; scheduler job `pantry-morning` created; budget present.

## 5. End-to-end in Telegram

| Step | Expected |
|------|----------|
| Send a fridge photo with no caption | Hebrew list within 15 s when warm; uncertain lines end with "?" |
| Send `מה יש לי במקרר?` | same items |
| Send `ביצים 4` | `עודכן: ביצים ×4`; a row in `pantry_corrections` |
| Send `להוסיף חומוס` | hummus ×1, correction kind `missed` |
| Send `להוסיף קולרבי` | asks whether to add a new item type |
| Message the bot from another account | no reply |
| Trigger the scheduler job by hand | morning message arrives |

```bash
gcloud scheduler jobs run pantry-morning --location europe-west1
```

## 6. Cost and privacy check

- `pantry_runs` rows hold counts, scores, cost and latency, no image fields.
- `gsutil lifecycle get gs://<bucket>` shows the 30-day delete on `photos/`.
- Cloud Logging for the service shows no photo bytes, captions or secret values.
