# Research: Pantry photo inventory

Phase 0 output for [plan.md](plan.md). Each entry: decision, rationale, alternatives considered.

## R1. Detector at serving time

- **Decision**: YOLO-World v2 small, with the item vocabulary fixed offline (`set_classes` on the ~30 English
  prompts from `config/items.yaml`) and exported to ONNX. The service runs it with `onnxruntime` on CPU at
  640 px. Ultralytics and PyTorch live only in the offline `training` dependency group, never in the
  runtime image. The fine-tuned YOLO later ships through the same ONNX path, so serving code does not change.
- **Rationale**: Constitution II (local detector first, CPU). An ONNX-only image is roughly a third of a
  torch image, which matters for cold start (SC-001) and Artifact Registry storage (Principle I). One
  inference on 1 vCPU is expected under 1 s.
- **Alternatives**: Ultralytics with torch CPU in the image (simpler, but ~1.5 GB image and slower cold
  start; kept as the fallback if the ONNX export of the open-vocabulary head fails); OWLv2 or Grounding DINO
  (stronger zero-shot, too slow on CPU); a hosted vision API for every photo (violates Principle II).
- **Risk to verify first**: ONNX export of YOLO-World with baked classes, and that its outputs match the
  `.pt` model on 5 photos. This is the first implementation task.

## R2. Fallback recognition step

- **Decision**: Claude Haiku 5.5 (`claude-haiku-5-5`, 0.10 USD input and 0.50 USD output per million
  tokens, from the claude-api skill model table cached 2026-10-06). Only crops whose detector score sits
  between `min_score` and `uncertain_score` are sent, padded 10 percent and resized so the long side is at
  most 384 px. One request per crop, run concurrently. Structured output via `output_config.format`:
  `{"item": <known item key> | "none", "count": int}`. Thinking disabled and effort `low`, since this is a
  classification route. A `refusal` stop reason, an API error or an exhausted budget leaves the item marked
  uncertain. Haiku 5.5 has no server-side refusal fallback, so none is configured.
- **Cost estimate**: a 384x288 crop is about 150 image tokens (width x height / 750); with the item-list
  prompt about 600 input tokens and 30 output tokens per call, so about 0.000075 USD per crop. At 30 photos
  a day and 3 uncertain crops each, about 0.20 USD a month.
- **Budget control**: a monthly counter in Firestore is checked before each call and incremented with the
  cost computed from `response.usage`. App cap 1.00 USD per month (config). The Anthropic key also gets a
  console spending limit set by the owner, which is the hard cap.
- **Alternatives**: Sonnet 5.5 (20x the price, not needed to name a crop); sending the whole photo (violates
  Principles II and IV); no fallback (FR-004 requires it).

## R3. Telegram transport and ordering

- **Decision**: Webhook to Cloud Run, raw `httpx` calls to the Bot API (same pattern as zchut-agent's
  `bot/telegram.py`), secret-token header checked on every request. `setWebhook` with `max_connections=1`
  and Cloud Run `concurrency=1`, `max-instances=1`, so updates are processed one at a time in order (edge
  case "photo while previous is processing"). The photo is processed inside the request, the reply is sent,
  then 200 is returned. Each `update_id` is recorded so a Telegram retry is a no-op.
- **Rationale**: Cloud Run allocates CPU only during a request by default, so work after a 200 would be
  throttled. Processing time (~4 s warm) is well under Telegram's webhook timeout.
- **Alternatives**: python-telegram-bot (heavier, own event loop); Cloud Tasks queue (another service for
  no v1 gain); long polling (needs an always-on process, violates scale-to-zero).

## R4. Location naming

- **Decision**: Caption word matched against aliases: מקרר / fridge, מקפיא / freezer, מזווה / pantry. No
  caption or no match means fridge. An album (`media_group_id`) inherits the caption of its first photo.
- **Source**: spec clarification 2026-10-20.

## R5. Multi-photo snapshot merge

- **Decision**: A photo joins the open snapshot of the same location when it arrives within 60 s of that
  snapshot's last photo, or shares its `media_group_id`. Counts are summed across the photos of a snapshot,
  since shelf-by-shelf photos show different shelves. After each photo the location's inventory is
  rewritten from the merged snapshot, and the reply shows the merged totals.
- **Alternatives**: max per item across photos (under-counts the same item on two shelves); waiting 60 s
  before replying (breaks the 15 s reply target).
- **Known limit**: overlapping photos double-count. The owner corrects, and the correction becomes a label.

## R6. Correction and query grammar

- **Decision**: Deterministic parser, no LLM (Principle II allows Claude only for crops). Text is normalised
  (Hebrew final letters, niqqud and punctuation stripped, English lowercased) and matched against item names
  and aliases from the item list. Grammar in [contracts/bot-commands.md](contracts/bot-commands.md). Unknown
  item names trigger a yes/no question with inline buttons before a new item type is created.
- **Target snapshot**: a reply to a bot message applies to that message's snapshot; otherwise the most
  recent snapshot of any location.

## R7. Uncertain items

- **Decision**: Uncertain items enter the inventory with `uncertain=true` and are shown with "?". Each
  uncertain line in the reply gets two inline buttons: confirm (clears the mark) and remove (count 0,
  recorded as a false detection). A text correction for that item also clears the mark.
- **Source**: spec clarification 2026-10-20.

## R8. Morning run-out message

- **Decision**: Cloud Scheduler job `30 7 * * *`, time zone Asia/Jerusalem, POSTs `/tasks/morning` with an
  OIDC token for a dedicated invoker service account; the app verifies the token audience and email.
  Run-out means count > 0 in the stored baseline and count 0 or absent now. After sending, the current
  inventory becomes the new baseline. With no baseline (first run) the message is "all good" and a
  baseline is written.
- **Alternatives**: Cloud Run IAM-only auth (impossible, the service must accept unauthenticated Telegram
  calls); comparing with yesterday's snapshots (fails on days without a photo).

## R9. Storage

- **Decision**: Firestore (existing default database, collections prefixed `pantry_`) for item types,
  snapshots, inventory, corrections, run records, budget and baselines. A private Cloud Storage bucket with
  uniform access, public access prevention, and a lifecycle rule deleting objects under `photos/` after 30
  days. Model files live under `models/` in the same bucket (no lifecycle) and are copied into the image at
  build time.
- **Alternatives**: a second Firestore database (the free tier covers the default database only);
  committing the ONNX file to git (~50 MB in a public repo).

## R10. Training data and the 30-day delete

- **Decision**: The service never keeps photos past 30 days (Principle IV, FR-012). The eval and training
  set lives outside the service: the owner's ~200 collection photos plus bot photos exported by an
  owner-run script (`scripts/export_dataset.py`) that downloads photos that have corrections before they
  expire. Labelling with Label Studio running locally; training on Colab or Kaggle from a private Drive
  folder.
- **Rationale**: Training is explicitly outside the service (Principle III), so a laptop step there does
  not break Principle V.
- **Alternatives**: a `dataset/` prefix without lifecycle (contradicts Principle IV as written, needs a
  constitution amendment); Roboflow free tier (projects are public, unacceptable for home photos).
- **Owner decision needed**: confirm this, or amend the constitution to allow a no-expiry `dataset/` prefix
  for photos the owner marks for training.

## R11. Eval

- **Decision**: `eval/run_eval.py` runs the ONNX detector over the labelled set and reports mAP@0.5,
  per-item precision and recall, and count accuracy (share of item occurrences whose predicted per-photo
  count equals the label). Runs on the owner's machine or Colab, never in the service. Output is a Markdown
  table for the README, zero-shot baseline vs fine-tuned (SC-002).

## R12. Cloud cost

| Item | Monthly estimate | Basis |
|------|------------------|-------|
| Cloud Run | 0.00 USD | ~27k vCPU-s, inside the 180k free tier shared with zchut |
| Firestore | 0.00 USD | far below 50k reads and 20k writes per day |
| Cloud Storage | 0.02 USD | under 1 GB in europe-west1 |
| Artifact Registry | 0.10 USD | ~0.4 GB image, cleanup policy keeps the last 2 |
| Cloud Scheduler | 0.00 USD | 1 job; zchut uses none of the 3 free jobs |
| Secret Manager | 0.00 to 0.10 USD | 3 secrets |
| Cloud Build | 0.00 USD | inside the free build-minutes |
| Claude Haiku 5.5 | 0.20 USD (app cap 1.00) | R2 |
| **Total** | **about 0.40 USD; at most 1.30 USD with the cap hit** | under the 10 USD cap |

GCP budget: a project budget at 10 USD with alerts at 50, 90 and 100 percent. A GCP budget alerts but does
not stop spend; the hard limits are `max-instances=1`, scale to zero, and the Anthropic key cap. Free-tier
figures are shared with zchut-agent on the same billing account and are re-checked at deploy.

## R13. Latency (SC-001)

Warm path estimate: Telegram file download 0.5 s, decode and detect 1 s, fallback crops in parallel 1.5 s,
Firestore writes 0.3 s, reply 0.3 s: about 4 s. Cold start adds container start, imports and ONNX session
load, estimated 4 to 8 s, measured separately per the clarification. Every run record stores `latency_ms`
and `cold_start`.
