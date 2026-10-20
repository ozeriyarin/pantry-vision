# Implementation Plan: Pantry photo inventory

**Branch**: `001-pantry-photo-inventory` (work stays on `main`, as in the other two projects) | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-pantry-photo-inventory/spec.md`

## Summary

A FastAPI service on Cloud Run receives Telegram webhooks from one allow-listed chat. A photo goes through a
YOLO-World zero-shot detector exported to ONNX and run on CPU; boxes in the uncertain score band are cropped
and checked by Claude Haiku 5.5 under a monthly cap. Results merge into a per-location snapshot (60 s window)
that rewrites the inventory in Firestore, and the bot replies in Hebrew. A deterministic Hebrew and English
grammar handles corrections and queries; every correction is stored with its snapshot as a training label.
Cloud Scheduler calls the service at 07:30 Asia/Jerusalem for the run-out message. Expiry tracking is out of
v1. Detection quality is measured offline on the owner's labelled photos. Details in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: FastAPI, uvicorn, httpx (Telegram Bot API), onnxruntime, numpy, Pillow,
google-cloud-firestore, google-cloud-storage, google-auth (OIDC check), anthropic, pydantic, PyYAML.
Offline only (`training` group, not in the image): ultralytics, torch. Dev: pytest, ruff.

**Storage**: Firestore default database, collections prefixed `pantry_`; private Cloud Storage bucket with a
30-day lifecycle delete on `photos/` ([data-model.md](data-model.md)).

**Testing**: pytest with fakes for Telegram, store, blob storage, detector, fallback and clock; runs offline
with no keys. ruff for lint.

**Target Platform**: Cloud Run (linux container), europe-west1, project `<GOOGLE_CLOUD_PROJECT in .env>`.

**Project Type**: web service (Telegram webhook bot) plus offline eval and training scripts.

**Performance Goals**: reply within 15 s for 95 percent of warm photos, about 4 s expected; cold starts
measured separately (R13).

**Constraints**: under 10 USD a month, about 0.40 USD expected (R12); 2 GiB memory, 1 vCPU, min 0, max 1
instance, concurrency 1; no image bytes in logs or run records; Hebrew owner-facing text.

**Scale/Scope**: one owner, about 30 photos a day, about 30 item types, three locations.

## Constitution Check

*GATE: checked before Phase 0 and again after Phase 1 design.*

| Principle | How the plan complies | Status |
|-----------|-----------------------|--------|
| I. Hard Budget Cap | Cost table in R12 (about 0.40 USD, worst case 1.30 USD). max-instances 1, scale to zero, Haiku app cap 1 USD plus the Anthropic console limit, GCP budget alert at 10 USD. Every fallback call writes `cost_usd`. | Pass |
| II. Cheap Model First | ONNX detector handles every photo; only crops in the uncertain band go to Haiku; thresholds in `config/settings.yaml`; corrections parsed without an LLM; calls counted in run records. | Pass |
| III. Measured, Not Claimed | `eval/run_eval.py` reports mAP@0.5, per-item precision and recall, count accuracy; zero-shot baseline row first, fine-tuned row later; training on Colab or Kaggle only. | Pass |
| IV. Privacy by Default | Private bucket, public access prevention, 30-day lifecycle on `photos/`; only crops leave GCP; run records hold no images; logs carry ids and types, never captions or bytes; allow-listed chat ids. | Pass (R10 confirmed: training photos stay outside the service) |
| V. Cloud-Native, Laptop-Free | Webhook, detector, storage and scheduler all in GCP; scripted `scripts/deploy.ps1`. Only training and eval touch the laptop, which the constitution places outside the service. | Pass |
| VI. Small, Testable Increments | Stories map to P1, P2, P3 task phases; each acceptance scenario gets a test quoting it; every external service behind a port with a fake. | Pass |

Post-design re-check: no new violations after the data model and contracts. Complexity Tracking stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-pantry-photo-inventory/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── http-endpoints.md
│   └── bot-commands.md
├── checklists/requirements.md
└── tasks.md              # /speckit-tasks, not created here
```

### Source Code (repository root)

```text
src/pantry/
├── app.py                # FastAPI routes: /telegram/webhook, /tasks/morning, /healthz
├── config.py             # settings from env + config/settings.yaml
├── ports.py              # Protocols: TelegramClient, Store, BlobStore, Detector, Verifier, Clock
├── domain/
│   ├── items.py          # item list, alias normalisation
│   ├── snapshot.py       # 60 s merge, inventory rewrite
│   ├── corrections.py    # apply count / missed / false / confirm
│   └── morning.py        # run-out against baseline
├── detection/
│   ├── onnx_detector.py  # YOLO-World ONNX on CPU
│   ├── quality.py        # dark or blurry photo check
│   ├── fallback.py       # Haiku crop check with budget guard
│   ├── pipeline.py       # detect, crop, verify, count
│   └── smoke.py
├── bot/
│   ├── commands.py       # Hebrew/English grammar to intents
│   ├── handlers.py       # photo, text, callback flows
│   └── texts.py          # every Hebrew string in one place
└── adapters/
    ├── telegram_http.py
    ├── firestore_store.py
    ├── gcs_blob.py
    └── anthropic_verifier.py

config/
├── items.yaml            # ~30 item types, aliases, prompts
└── settings.yaml         # thresholds, merge window, caps, schedule

eval/run_eval.py, eval/metrics.py
training/export_onnx.py, training/finetune.ipynb
scripts/deploy.ps1, scripts/export_dataset.py
Dockerfile, cloudbuild.yaml, pyproject.toml

tests/
├── fakes.py
├── unit/                 # grammar, merge, corrections, morning, metrics, budget
├── integration/          # FastAPI TestClient end to end with fakes, one test per acceptance scenario
└── contract/             # webhook auth, allow-list, scheduler OIDC, duplicate update_id
```

**Structure Decision**: one Python package under `src/pantry` with ports and adapters, mirroring
zchut-agent's layout and deploy pattern (`Dockerfile`, `cloudbuild.yaml` with CLOUD_LOGGING_ONLY, a dedicated
build service account, `scripts/deploy.ps1` under pwsh 7). The model file is pulled from
`gs://<bucket>/models/` during the Cloud Build step, never committed.

## Delivery order

1. **Spike**: export YOLO-World v2 small with the 30 classes to ONNX and compare with the `.pt` model on 5
   photos (R1). If it fails, switch to torch CPU in the image and re-cost the image size.
2. **P1**: ports, fakes, detector, pipeline, snapshot merge, inventory, queries, webhook auth, allow-list.
3. **P1 fallback**: Haiku verifier, budget guard, run records.
4. **P2**: correction grammar, callbacks, new-item question, correction records.
5. **P3**: morning endpoint, OIDC check, baseline.
6. **Deploy**: bucket, lifecycle, service accounts, secrets, Cloud Run, webhook, scheduler, budget.
7. **Eval**: zero-shot baseline on the labelled set, README table.

## Owner inputs needed

| Needed by | Item |
|-----------|------|
| Step 1 | about 5 fridge photos for the export comparison |
| Step 6 | Telegram bot from BotFather; Anthropic key with its own spending limit (suggest 2 USD a month) |
| Step 6 | GitHub repository visibility (public fits the AGPL detector licence) |
| Step 7 | about 150 labelled photos |

## Complexity Tracking

No constitution violations to justify.
