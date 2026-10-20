---

description: "Task list for spec 001 pantry photo inventory"
---

# Tasks: Pantry photo inventory

**Input**: Design documents from `specs/001-pantry-photo-inventory/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. Constitution Principle VI: every acceptance criterion has a test whose docstring quotes
it, and `pytest` runs offline with fakes and no keys. Write each story's tests first and see them fail.

**Organization**: grouped by user story so each story ships and tests on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1, US2, US3 from spec.md
- Paths are from the repository root, single-project layout per plan.md

## Commit gate

Before every commit: `uv run pytest` and `uv run ruff check` pass, chained with hard stops. Message format
`<prefix>/<dd-mm-yy hh-mm> - <what it does>`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: project skeleton, config files, tooling

- [X] T001 Create `pyproject.toml` for package `pantry` under `src/` (Python >=3.11): runtime deps fastapi, uvicorn, httpx, onnxruntime, numpy, pillow, google-cloud-firestore, google-cloud-storage, google-auth, anthropic, pydantic, pyyaml; `[dependency-groups]` `dev` (pytest, ruff) and `training` (ultralytics, torch), training never installed in the image; ruff and pytest config (`testpaths = ["tests"]`); create empty `src/pantry/__init__.py`, `tests/__init__.py`; run `uv lock`
- [X] T002 [P] Extend `.gitignore` with `.env`, `models/`, `*.onnx`, `*.pt`, `data/`, `*.jpg`, `*.jpeg`, `*.png`, `eval/out/`
- [X] T003 [P] Create `.env.example` listing setting names only, no values: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_REGION`, `TELEGRAM_ALLOWED_CHAT_IDS`, `PANTRY_BUCKET`, `PANTRY_TELEGRAM_BOT_TOKEN`, `PANTRY_TELEGRAM_WEBHOOK_SECRET`, `PANTRY_ANTHROPIC_API_KEY`
- [X] T004 [P] Create `config/items.yaml` with about 30 item types, each with `key` ("lowercase ascii slug, unique"), `name_he`, `aliases` (Hebrew and English, "unique across all types"), `prompt` (English detector prompt), `location_hint` (fridge, freezer, pantry or null); include eggs/ביצים, milk/חלב, cottage/קוטג', hummus/חומוס, yogurt/יוגורט (brands grouped)
- [X] T005 [P] Create `config/settings.yaml`: `min_score`, `uncertain_score`, `session_window_s: 300`, `fallback.cap_usd: 1.00`, `fallback.model: claude-haiku-5-5`, `fallback.price_in_per_mtok: 0.10`, `fallback.price_out_per_mtok: 0.50`, `crop.pad: 0.10`, `crop.max_side: 384`, `quality.min_luminance`, `quality.min_laplacian_var`, `morning.tz: Asia/Jerusalem`, `pending_ttl_min: 10`, `detector.imgsz: 640`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the ONNX spike, config, ports, fakes, item catalogue, webhook shell. No story work before this ends.

- [X] T006 Write `training/export_onnx.py` (training group only): load `yolov8s-worldv2.pt`, `set_classes` with the `prompt` list from `config/items.yaml` in file order, export ONNX at imgsz 640, write `models/<name>.onnx` plus `models/<name>.json` holding the class-key order and sha256 (research R1)
- [X] T007 Write `training/compare_export.py`: run the `.pt` and the `.onnx` on the owner's 5 spike photos and print per-photo box count and score deltas; record the outcome under R1 in `specs/001-pantry-photo-inventory/research.md` (if the export fails, switch plan to torch CPU in the image and re-cost R12 before continuing)
- [X] T008 Implement `src/pantry/config.py`: settings model loaded from env plus `config/settings.yaml`; secret values read from env only and never included in `repr` or logs
- [X] T009 [P] Implement `src/pantry/domain/models.py` dataclasses per data-model.md: `ItemType` (`added_by` "seed" or "owner"), `Detection` (`box`, `score`, `fallback`), `Snapshot` (`items` map with `count`, `score`, `uncertain`, `source` "detector"/"fallback"), `InventoryEntry` (`count` "int >= 0; 0 means known run out", `uncertain`, `last_seen_at`, `snapshot_id`), `Correction` (`kind` "count / missed / false / confirm"), `RunRecord` (no image fields), `Budget`, `Baseline`, `PendingQuestion`; `Location` enum fridge, freezer, pantry
- [X] T010 [P] Implement `src/pantry/ports.py` Protocols: `TelegramClient`, `Store`, `BlobStore`, `Detector`, `Verifier`, `Clock`
- [X] T011 Implement `tests/fakes.py`: `FakeTelegram` (records sent messages and keyboards), `InMemoryStore`, `FakeBlob`, `FakeDetector` (scripted detections per photo), `FakeVerifier` (scripted answers, refusal, error), `FakeClock`; shared fixtures in `tests/conftest.py` building the app with fakes
- [X] T012 [P] Implement `src/pantry/domain/items.py`: `normalise()` (fold Hebrew final letters, strip niqqud and punctuation, lowercase English) and `ItemCatalog.resolve(name)` over names and aliases; test in `tests/unit/test_items.py` quoting the edge case "Hebrew and English item names in corrections ("milk" / "חלב") map to the same item type"
- [X] T013 [P] Create `src/pantry/bot/texts.py` holding every Hebrew string from `contracts/bot-commands.md`, as functions taking counts and names
- [X] T014 [P] Implement `src/pantry/adapters/telegram_http.py` with httpx: `get_file`, `download`, `send_message` (optional inline keyboard), `answer_callback_query`, `edit_message_reply_markup`; Update parsing for message, photo, caption, `media_group_id`, `reply_to_message`, callback query (pattern from `C:\zchut-agent\src\zchut\bot\telegram.py`)
- [X] T015 Implement `src/pantry/app.py` shell: `GET /healthz`; `POST /telegram/webhook` checking `X-Telegram-Bot-Api-Secret-Token` in constant time (401 on mismatch), allow-list check before any data access, duplicate `update_id` guard in `pantry_updates`, dispatch to handlers, always `200 {"ok": true}` after auth with errors logged by type only and a short Hebrew error reply
- [X] T016 [P] Contract tests in `tests/contract/test_webhook.py`: wrong secret gives 401; "Given a message from any chat that is not the owner's, When it arrives, Then the bot does not process it and does not reply with any inventory data"; a repeated `update_id` is a no-op; a handler exception still returns 200
- [X] T017 [P] Implement `src/pantry/adapters/firestore_store.py` (collections prefixed `pantry_`, budget increment in a transaction) and `src/pantry/adapters/gcs_blob.py` (writes `photos/yyyy/mm/dd/<uuid>.jpg`, never logs bytes)

**Checkpoint**: tests and lint pass on an app that authenticates, filters and replies to nothing yet.

---

## Phase 3: User Story 1 - Photo to inventory (Priority: P1) 🎯 MVP

**Goal**: a photo with an optional caption location becomes a Hebrew item list and the location's inventory; the owner can query it.

**Independent Test**: send a known photo; the reply lists the expected items and counts, and the inventory query returns the same list.

### Tests for User Story 1 (write first, see them fail)

- [ ] T018 [P] [US1] Integration tests in `tests/integration/test_us1_photo.py`, one per acceptance scenario with its text quoted: 6 eggs and 2 milk reply "ביצים ×6" and "חלב ×2" and the fridge query returns the same; low-certainty item marked "?"; no food found leaves inventory unchanged; plus caption מקפיא routes to freezer, no caption means fridge
- [ ] T019 [P] [US1] Edge-case tests in `tests/integration/test_us1_edges.py`: blurry or dark photo asks for a retake and leaves inventory unchanged; a door photo without milk and no "סיימתי" keeps milk (Story 1 scenario 5, quoted); "סיימתי" sets unseen fridge items to 0 and lists them (scenario 6, quoted); overlapping photos merge by highest count; a photo after the window opens a new session; album photos share a session by `media_group_id`; fallback skipped for budget reports "k פריטים לא נבדקו שוב"
- [ ] T020 [P] [US1] Unit tests in `tests/unit/test_snapshot.py`: session window, `media_group_id`, highest-count merge, seen-item upsert, timeout close zeroes nothing, `full` close sets absent items of that location to 0, uncertain flag carried into the inventory
- [ ] T021 [P] [US1] Unit tests in `tests/unit/test_fallback.py`: only scores in `[min_score, uncertain_score)` are sent; spend at or above cap skips the call; cost computed from usage at 0.10 / 0.50 USD per million tokens and added to the budget; `refusal` and API errors leave the item uncertain; verifier answer "none" drops the box
- [ ] T022 [P] [US1] Unit tests in `tests/unit/test_commands_query.py`: "מה יש לי", "מה יש לי במקרר", "יש ביצים?", "יש ביצים" parse to the right intents; caption location parsing

### Implementation for User Story 1

- [ ] T023 [P] [US1] Implement `src/pantry/detection/onnx_detector.py`: load the ONNX file and its JSON sidecar, letterbox to 640, run onnxruntime on CPU, decode boxes, NMS, map class index to item key; expose model name and sha256 prefix
- [ ] T024 [P] [US1] Implement `src/pantry/detection/quality.py`: mean luminance and Laplacian variance against the settings thresholds
- [ ] T025 [US1] Implement `src/pantry/detection/fallback.py`: pad 10 percent, resize long side to 384, budget check before each call, concurrent calls, budget increment after; and `src/pantry/adapters/anthropic_verifier.py`: `claude-haiku-5-5`, structured output `{"item": <known key> | "none", "count": int}` via `output_config.format` with the key enum, thinking disabled, effort `low`, check `stop_reason` before reading content
- [ ] T026 [US1] Implement `src/pantry/detection/pipeline.py`: quality check, detect, drop below `min_score`, certain at or above `uncertain_score`, verify the band in between, return counts per key with score, uncertain flag and source
- [ ] T027 [US1] Implement `src/pantry/domain/snapshot.py`: join or open a session ("now - last_photo_at <= session_window_s" or same `media_group_id`), merge by highest count, upsert seen items after each photo, close as full ("סיימתי") or partial (timeout, checked lazily on the next message), store `reply_message_ids`
- [ ] T028 [US1] Implement query, caption and "סיימתי"/"done" parsing in `src/pantry/bot/commands.py`
- [ ] T029 [US1] Implement photo and query flows in `src/pantry/bot/handlers.py`: download largest photo size, store blob, pipeline, snapshot, reply with running totals, the "סיימתי" hint, uncertain lines ending " ?" plus `✓`/`✗` buttons (`confirm:<snapshot>:<key>`, `remove:<snapshot>:<key>`), "not checked" line when fallback skipped, then a `RunRecord` with counts, scores, fallback calls, skipped, cost, `latency_ms`, `cold_start`
- [ ] T030 [US1] Implement `src/pantry/detection/smoke.py` CLI per quickstart step 2

**Checkpoint**: US1 tests green; the MVP answers photos and queries.

---

## Phase 4: User Story 2 - Correct the bot (Priority: P2)

**Goal**: short Hebrew or English replies and button taps fix the inventory immediately and leave a labelled correction.

**Independent Test**: after a photo reply, send "ביצים 4"; the inventory shows 4 eggs and a correction record links the photo to the corrected count.

### Tests for User Story 2 (write first, see them fail)

- [ ] T031 [P] [US2] Integration tests in `tests/integration/test_us2_corrections.py`, scenarios quoted: "ביצים 4" sets 4 and confirms; "להוסיף חומוס" adds hummus ×1 recorded as `missed`; unknown item asks before adding, `כן` creates an `owner` item type and applies, `לא` changes nothing; "no milk" works like "אין חלב"; `✓` clears uncertain with kind `confirm`; `✗` sets 0 with kind `false`
- [ ] T032 [P] [US2] Unit tests in `tests/unit/test_commands_corrections.py` for every row of the corrections table in `contracts/bot-commands.md`, both word orders for counts, and the fallback "לא הבנתי" reply
- [ ] T033 [P] [US2] Unit tests in `tests/unit/test_corrections.py`: target snapshot from `reply_to_message` else the latest snapshot; `old_count`/`new_count` recorded; any correction clears `uncertain`; pending question expires after 10 minutes

### Implementation for User Story 2

- [ ] T034 [US2] Add correction patterns to `src/pantry/bot/commands.py` (`<item> <n>`, `<n> <item>`, `אין <item>`, `no <item>`, `להוסיף <item> [<n>]`, `add <item> [<n>]`)
- [ ] T035 [US2] Implement `src/pantry/domain/corrections.py`: resolve target snapshot, apply to the inventory entry, choose kind (`false` when the item was detected and set to 0, `missed` when it was not detected), write the `Correction`
- [ ] T036 [US2] Implement text-correction, callback and new-item flows in `src/pantry/bot/handlers.py` using `PendingQuestion` in `pantry_pending/{chat_id}`; answer every callback query and remove the used buttons

**Checkpoint**: US1 and US2 tests green.

---

## Phase 5: User Story 3 - Morning heads-up (Priority: P3)

**Goal**: one Hebrew message each morning listing items that ran out since the previous morning, or "all good".

**Independent Test**: seed yesterday's baseline with milk and a current inventory without it; the morning message lists milk as run out.

### Tests for User Story 3 (write first, see them fail)

- [ ] T037 [P] [US3] Integration tests in `tests/integration/test_us3_morning.py`, scenarios quoted: milk in the baseline and absent now is listed as run out; nothing ran out sends the one-line "all good"; first run with no baseline sends "all good" and writes one; a second call on the same Asia/Jerusalem date sends nothing; a partial session that did not show milk does not list milk as run out (Story 3 scenario 3, quoted)
- [ ] T038 [P] [US3] Contract tests in `tests/contract/test_morning_auth.py`: missing token, wrong audience and wrong service-account email each give 401 (token verifier injected as a fake)

### Implementation for User Story 3

- [ ] T039 [US3] Implement `src/pantry/domain/morning.py`: run-out = "count > 0 in the stored baseline and count 0 or absent now", new baseline after sending, last-sent date for idempotency
- [ ] T040 [US3] Add `POST /tasks/morning` to `src/pantry/app.py`: verify the OIDC token with `google.oauth2.id_token` against the service URL audience and the `pantry-scheduler` email, send to each allow-listed chat, return `{"sent": n, "run_out": k}`

**Checkpoint**: all three stories green offline.

---

## Phase 6: Deploy

**Purpose**: run it in the cloud (Principle V). Needs the owner's bot token and capped Anthropic key.

- [ ] T041 Create `Dockerfile` (python:3.11-slim, non-root user, runtime deps only, copies `config/` and `models/`) and `cloudbuild.yaml` (step copying `gs://$_BUCKET/models/` into the build context, then build and push, `logging: CLOUD_LOGGING_ONLY`), following `C:\zchut-agent`
- [ ] T042 Write `scripts/seed_items.py`: upsert `config/items.yaml` into `pantry_item_types`, never deleting `added_by: owner` types
- [ ] T043 Write `scripts/deploy.ps1` (pwsh 7, Cloud SDK on PATH, values from `.env`, never printed) with steps `check`, `setup` (APIs; private bucket with public access prevention and 30-day delete on `photos/`; service accounts `pantry-bot`, `pantry-build`, `pantry-scheduler` with least roles; Artifact Registry repo with keep-2 cleanup; Firestore TTL on `pantry_updates.received_at`; composite index on `pantry_snapshots` (location asc, last_photo_at desc)), `secrets`, `build`, `deploy` (min 0, max 1, concurrency 1, 2 GiB, 1 vCPU, timeout 60 s), `webhook` (`setWebhook` with secret, `max_connections=1`, `allowed_updates`), `scheduler` (`pantry-morning`, `30 7 * * *`, Asia/Jerusalem, OIDC), `budget` (10 USD, alerts 50/90/100 percent), `all`
- [ ] T044 Deploy from a pushed commit and run the detector smoke test on the five spike photos first, then quickstart steps 4 to 6; record cold and warm reply times from `pantry_runs`; send two photos back to back and confirm two replies in send order (edge case "processed in order, each gets its own reply")

---

## Phase 7: Eval, dataset and polish

- [ ] T045 [P] Implement `eval/metrics.py` (mAP@0.5, per-item precision and recall, count accuracy) with `tests/unit/test_metrics.py` on hand-computed fixtures
- [ ] T046 Implement `eval/run_eval.py` per quickstart step 3, writing a Markdown table to `eval/out/`
- [ ] T047 [P] Write `scripts/export_dataset.py` (owner-run, research R10): download photos that have corrections before the 30-day delete, plus detections and corrections as JSON for Label Studio pre-annotation, into a local folder outside the repo
- [ ] T048 [P] Write `training/finetune.ipynb` for Colab or Kaggle (private workspace per constitution v1.1.0, Principle IV): train from the labelled export, export ONNX via the T006 path
- [ ] T049 [P] Privacy tests in `tests/contract/test_privacy.py`: `RunRecord` has no image fields; captured logs during a photo flow hold no caption text, image bytes or secret values
- [ ] T050 Run the zero-shot eval on the labelled set and write `README.md`: what it does, architecture, cost table from R12, eval table with the zero-shot baseline row, privacy notes, Ultralytics AGPL note
- [ ] T051 Close the spec: set `**Status**` in `specs/001-pantry-photo-inventory/spec.md` to shipped with the deployed commit sha, and update the State section of `CLAUDE.md`

---

## Dependencies & Execution Order

- **Setup (T001–T005)** first. T002–T005 run in parallel after T001.
- **Foundational (T006–T017)** blocks every story. T006–T007 is the spike and gates T023; T008–T017 can proceed alongside it.
- **US1 (T018–T030)** after Foundational. MVP.
- **US2 (T031–T036)** needs US1's snapshots and inventory (T027, T029) but not US3.
- **US3 (T037–T040)** needs only the inventory and store from Foundational plus T027; it can run alongside US2.
- **Deploy (T041–T044)** after the stories you want live; can ship after US1 alone.
- **Eval (T045–T050)** T045, T047–T049 any time after Foundational; T046 after T023; T050 needs the labelled photos.
- **T051** last.

Within a story: tests, then domain, then detection or parsing, then handlers.

## Parallel Examples

```text
US1 tests together:  T018, T019, T020, T021, T022
US1 then:            T023 and T024 together, then T025 → T026 → T027 → T028 → T029
US2 tests together:  T031, T032, T033
US3 alongside US2:   T037 and T038 together, then T039 → T040
Foundational:        T009, T010, T012, T013, T014, T016, T017 together after T008
```

## Implementation Strategy

1. **MVP**: Setup, Foundational, US1, then deploy (T041–T044). Stop and use it for a few days while
   collecting photos.
2. **Increment 2**: US2 corrections, redeploy. Corrections start producing labels.
3. **Increment 3**: US3 morning message, redeploy, start the two-week trial for SC-005.
4. **Measure**: zero-shot eval and README table, then fine-tune in a later spec.

Each increment is its own commit set with the gate, and each deploy maps to a pushed sha.
