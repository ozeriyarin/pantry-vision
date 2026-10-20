# CLAUDE.md

Guidance for Claude Code in this repo.

## What this is

Pantry Vision: a Hebrew Telegram bot for one owner (Yarin Ozeri). Send a photo of the fridge, freezer or
pantry, get back recognised items with counts, correct mistakes with short replies, keep an inventory per
location, and get a 07:30 morning message about items that ran out. Third portfolio project for
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
- No expiry tracking in v1 (decided 2026-10-20); the morning message lists run-out items only.
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
  (P1 photo to inventory, P2 corrections, P3 morning heads-up) with its quality checklist. Commit 07d995e.
- GitHub: public repo `ozeriyarin/pantry-vision` (owner decision 2026-10-20). Keep private data out: photos,
  models, `.env`, the GCP project id and the chat id live only in the gitignored `.env`. `gh` is at
  `C:\Program Files\GitHub CLI\gh.exe`.
- 2026-10-20: spec 001 clarified (no expiry in v1, caption location, uncertain items kept, 80% is the
  fine-tuned target, cold starts exempt). Plan done: YOLO-World ONNX on CPU, Haiku 5.5 crop fallback,
  about 0.40 USD a month. R10 confirmed: training photos exported by an owner-run script.
- Tasks: 51 in `specs/001-pantry-photo-inventory/tasks.md` (MVP = setup, foundational, US1, deploy).
- 2026-10-20: setup and ONNX spike done (T001-T007): export is faithful, zero-shot quality looks weak.
  Ultralytics analytics turned off (`yolo settings sync=False`). Run tools with `python -m uv`.
- 2026-10-20: foundational T008-T017 done (32 tests). httpx logger is silenced in app.py because Telegram
  URLs carry the bot token.
- 2026-10-20: US1 T018-T030 done (90 tests). One real Haiku crop call verified the request shape
  (0.0001 USD). Labels are weak at both steps (labneh read as tahini, yogurt as ice cream): tune prompts
  before the baseline eval.
- 2026-10-20: US2 T031-T036 done (124 tests).
- 2026-10-20: US3 T037-T040 done (142 tests). All three stories pass offline.
- 2026-10-20: deployed with `pwsh -File scripts/deploy.ps1` (steps check, setup, secrets, model, build,
  deploy, webhook, scheduler, budget). Service pantry-bot, revision 2, scale 0-1, concurrency 1. Webhook set,
  scheduler 07:30 verified (OIDC 200). Budget 37 ILS (billing account is ILS, about 10 USD), label
  app=pantry-vision. Cloud Run reserves /healthz, so health is /health. Cold start about 13 s.
- 2026-10-20: first real photo scored 4/10 by the owner; buttons failed on a Telegram refresh error.
  Revision 3 fixes: button refresh is cosmetic and logs Telegram's reason, one label per object, min score
  0.20, "soy sauce bottle" prompt, correction hint in replies, CPU boost. Right after a deploy, Cloud Run
  may answer 429 for a minute while the single instance churns.
- 2026-10-20: multi-line corrections, plurals, "did you mean", location prefix ("מקפיא: גלידה 2") live.
  T045-T049 done (metrics, eval runner, dataset export, Colab notebook, privacy tests); README written with
  accuracy table pending. Bash heredocs on this machine turn "\n" into a real newline: edit such lines
  with the Edit tool.
- 2026-10-20: configurable locations live (revision 7): built-ins in config/locations.yaml, owner adds more
  with "מיקום חדש: <name>", stored in pantry_locations. Took +231 / -81 against a +100 / -40 estimate.
- Open: T050 needs the zero-shot eval on about 150 labelled photos; T051 closes the spec.
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
