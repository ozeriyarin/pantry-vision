# CLAUDE.md

Guidance for Claude Code in this repo.

## What this is

Pantry Vision: a Hebrew Telegram bot for one owner (Yarin Ozeri). Send a photo of the fridge, freezer or
pantry, get back recognised items with counts, correct mistakes with short replies, keep an inventory per
location, and get a 07:30 morning message about items expiring soon or run out. Third portfolio project for
an AI-engineering interview at M.ai by Moveo (conversational AI). The other two are `C:\morning-agent`
(TypeScript, Agent OS) and `C:\zchut-agent` (Python RAG, Agent OS, Cloud Run).

The point of this project: show a non-LLM AI skill (computer vision: zero-shot detection, then fine-tuning,
with a real eval) and a second spec-driven framework (GitHub spec-kit) to compare with Agent OS.

## Owner decisions (2026-10-20, locked)

- Framework: GitHub spec-kit (specify-cli 1.2.2, Claude integration). Not Agent OS.
- Runs fully in the cloud; nothing in normal operation depends on the owner's laptop.
- Hebrew user-facing text; code, docs and commits in English.
- Single user (allow-listed Telegram chat id). Family sharing later.
- No barcode scanning in v1. Recipes come after v1.
- Budget: under 10 USD per month, hard caps at every provider.

## Planned stack (to be confirmed in /speckit-plan)

- Python 3.11, FastAPI, `uv`, `pytest`, `ruff`.
- Detector: YOLO-World zero-shot on CPU first; later a YOLO fine-tuned on the owner's labelled photos,
  exported to ONNX. Training on free Colab or Kaggle GPU, never in the service. Ultralytics is AGPL-3.0.
- Fallback: Claude Haiku vision only on crops below the confidence threshold, with a monthly cap.
  Verify current model ids and prices with the claude-api skill before writing them into the plan.
- Google Cloud (existing project `<GOOGLE_CLOUD_PROJECT in .env>`, region europe-west1, shared with
  zchut-agent): Cloud Run (scale to zero, Telegram webhook), Firestore (inventory, corrections, run
  records), Cloud Storage (private bucket, 30-day lifecycle delete), Cloud Scheduler (morning message),
  Secret Manager, a GCP budget alert. Reuse zchut's deploy pattern: `C:\zchut-agent\scripts\deploy.ps1`,
  `cloudbuild.yaml` with CLOUD_LOGGING_ONLY, a dedicated build service account, run under pwsh 7, Cloud SDK at
  `C:\Users\User\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin` (prepend to PATH).
- Eval: about 150 owner-labelled photos; mAP@0.5, per-item precision and recall, count accuracy; zero-shot vs
  fine-tuned table in the README.

## Workflow (spec-kit)

`/speckit-specify` → `/speckit-clarify` (if ambiguous) → `/speckit-plan` → `/speckit-tasks` →
`/speckit-analyze` → `/speckit-implement`. The constitution is `.specify/memory/constitution.md` (v1.0.0, six
principles); every plan needs its Constitution Check. Specs live in `specs/NNN-name/`; the active one is in
`.specify/feature.json`. Gate before every commit: `pytest` and `ruff check` pass. Close a spec with its
shipped commit sha.

## State

- 2026-10-20: spec-kit init, constitution v1.0.0, spec `specs/001-pantry-photo-inventory/spec.md`
  (P1 photo to inventory, P2 corrections, P3 morning heads-up) with its quality checklist. Commit e5a894c.
- No GitHub remote yet: the owner is choosing public or private (the other two projects are public under
  `ozeriyarin`). Use `gh` at `C:\Program Files\GitHub CLI\gh.exe` once chosen.
- Next: owner reviews spec 001, then `/speckit-plan`.
- Owner tasks: collect about 200 photos over two weeks (fridge, freezer, pantry, varied fill and light);
  create a new Telegram bot with BotFather; create a dedicated Anthropic key with its own spending cap.

## Owner's working rules

- Reply in English, even when the owner writes Hebrew.
- Never print, log or commit secret values; secrets live in Secret Manager and a gitignored `.env`.
- Every paid provider must be prepaid or hard-capped; state the monthly cost of anything new.
- Never change system or security settings on the owner's machine.
- Run sub-agents in the background so the owner can keep talking.
- Report change size as source +added / −removed lines, tests counted separately, never only net.
- Comments: one short line, only where the reason is not obvious.
- Commit messages: `<prefix>/<dd-mm-yy hh-mm> - <what it does>`, prefix in feature, fix, logs, debugging,
  crucial-adds. Use hard-stop gates in shell chains so a failing test never gets committed.
- The owner allows deploys of this project from the agent's shell, but never anything on CommunicatePOS,
  commu.click or the commit-ai production account.
- When an ask turns out bigger than it looked, stop and say the size before building.
