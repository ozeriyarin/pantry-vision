# Pantry Vision Constitution

## Core Principles

### I. Hard Budget Cap (NON-NEGOTIABLE)

Total running cost stays under 10 USD per month. Every paid provider is prepaid or has a hard spending limit
(GCP budget alert plus scale-to-zero Cloud Run, a dedicated Anthropic key with its own cap). Every paid call
records its cost in the run record. A feature that cannot show its monthly cost estimate does not ship.

### II. Cheap Model First, LLM on Fallback

The local detector (YOLO-World, later a fine-tuned YOLO exported to ONNX) runs on CPU and handles every photo.
The Claude vision model is called only for crops below the configured confidence threshold, never for the
whole photo by default. The threshold lives in config, and every fallback call is counted.

### III. Measured, Not Claimed

A detection change ships only with an eval on the owner's labelled photo set: mAP@0.5, per-item precision and
recall, and count accuracy, before and after. The first deployed detector is the baseline: its eval runs as
soon as the labelled set exists. Numbers go in the README. Training happens on a free GPU
(Colab or Kaggle) outside the service; serving never trains.

### IV. Privacy by Default

Photos of the owner's home are private data. Photos are stored only in a private bucket with a 30-day
lifecycle delete, never logged, never committed, and never sent to any provider except the fallback crop
and the owner's private training workspace (a private Drive folder used from Colab, or a private Kaggle
dataset) for photos the owner exports for labelling and training.
Run records keep counts and labels, not images. Single user: only allow-listed Telegram chat ids are served.

### V. Cloud-Native, Laptop-Free

Everything the owner uses runs in Google Cloud: the bot webhook and detector on Cloud Run, inventory in
Firestore, photos in Cloud Storage, the daily message from Cloud Scheduler. Nothing in normal operation
depends on the owner's machine being on. Deploys are scripted and repeatable.

### VI. Small, Testable Increments

Each spec is one usable step with numbered acceptance criteria; every criterion has a test that quotes it.
External services (Telegram, Claude, Firestore, Storage) sit behind interfaces with fakes, so `pytest` runs
offline with no keys.

## Technical Constraints

- Python 3.11, FastAPI, `uv` for dependencies, `pytest`, `ruff`. Ultralytics YOLO (AGPL-3.0; the repo is public).
- Hebrew user-facing text (bot replies, item names shown to the owner); code, docs and commits in English.
- Secrets only in Secret Manager and a gitignored local `.env`; never printed, logged or committed.
- Comments are one short line, only where the reason is not obvious.

## Development Workflow

- Spec Kit flow per feature: `/speckit-specify` → `/speckit-clarify` when anything is ambiguous →
  `/speckit-plan` → `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement`.
- Gate before every commit: `pytest` and `ruff check` pass. A spec is closed with its shipped commit sha.
- Deploy only committed and pushed code; the deployed revision maps to a pushed sha.

## Governance

This constitution overrides other practices in this repo. Amendments change this file in their own commit with
a version bump (MAJOR for removed or redefined principles, MINOR for new principles or sections, PATCH for
wording) and a one-line reason. Every plan includes a Constitution Check against Principles I–VI; a violation
needs a written justification in the plan's Complexity Tracking table or the plan is rejected.

**Version**: 1.1.0 | **Ratified**: 2026-10-20 | **Last Amended**: 2026-10-20
