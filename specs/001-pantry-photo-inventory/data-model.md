# Data model: Pantry photo inventory

Phase 1 output for [plan.md](plan.md). Firestore collections are prefixed `pantry_`. Times are UTC
timestamps; display uses Asia/Jerusalem. Locations: `fridge`, `freezer`, `pantry`.

## Location — `config/locations.yaml` + `pantry_locations/{key}`

`{key, name_he, aliases, added_by: "seed" | "owner"}`. Keys `fridge`, `freezer`, `pantry` are built in and fridge
is the default; owner-added keys are `loc_<hex>`. Every `location` field below holds one of these keys.

## ItemType — `pantry_item_types/{key}`

Seeded from `config/items.yaml` on deploy (upsert, never deletes owner-added types).

| Field | Type | Rules |
|-------|------|-------|
| key | str | doc id, lowercase ascii slug, unique (`eggs`) |
| name_he | str | shown to the owner (`ביצים`) |
| aliases | list[str] | Hebrew and English, normalised, unique across all types |
| prompt | str | English detector prompt (`egg`); empty for owner-added types until retraining |
| location_hint | str or null | one of the locations |
| added_by | `seed` or `owner` | |

FR-009: the list is data, editable in `config/items.yaml` or by the bot's new-item flow.

## Snapshot — `pantry_snapshots/{id}`

| Field | Type | Rules |
|-------|------|-------|
| location | str | one of the locations |
| opened_at, last_photo_at | timestamp | a photo joins when `now - last_photo_at <= session_window_s` (default 300) or same `media_group_id` |
| media_group_id | str or null | |
| photos | list[{blob_path, telegram_file_id, detections}] | blob path only, never image bytes |
| items | map[key -> {count:int, score:float, uncertain:bool, source:`detector`/`fallback`}] | highest count per item across photos |
| closed_by | `done` / `timeout` / null | null while open |
| full | bool | true only when closed by "סיימתי" / "done" |
| reply_message_ids | list[int] | lets a reply-to correction find its snapshot |

Each detection: `{key, box:[x1,y1,x2,y2], score, fallback: null | {item, count, cost_usd}}`.

States: `open` within the session window; `closed` by "סיימתי" (full) or by timeout (partial). A new photo on an empty result
(no food found) creates no snapshot and leaves inventory unchanged (Story 1, scenario 3).

## InventoryEntry — `pantry_inventory/{location}__{key}`

| Field | Type | Rules |
|-------|------|-------|
| location, key | str | |
| count | int | >= 0; 0 means known run out |
| uncertain | bool | cleared by confirm button or any correction on this item |
| last_seen_at | timestamp | |
| snapshot_id | str | last snapshot that set it |

Seen items are upserted after each photo of a snapshot (FR-005). Absent items of the location are set to
count 0 only when the snapshot closes with `full=true`. Corrections update a single entry immediately
(FR-007).

## Correction — `pantry_corrections/{id}`

| Field | Type | Rules |
|-------|------|-------|
| snapshot_id | str | required; links to photos (FR-008) |
| key | str | item type |
| kind | `count` / `missed` / `false` / `confirm` | `missed`: detector had 0; `false`: owner set 0 on a detected item |
| old_count, new_count | int | |
| created_at | timestamp | |
| text | str | owner's raw text, Hebrew allowed |

## RunRecord — `pantry_runs/{id}`

One per processed photo (FR-013). No image data.

| Field | Type |
|-------|------|
| snapshot_id, location | str |
| detector_model | str (ONNX file name + sha256 prefix) |
| counts | map[key -> int] |
| scores | map[key -> list[float]] |
| uncertain_count, fallback_calls, fallback_skipped | int |
| fallback_cost_usd | float |
| latency_ms | int |
| cold_start | bool |
| created_at | timestamp |

SC-004: monthly cost is the sum of `fallback_cost_usd` plus the GCP bill.

## Budget — `pantry_budget/{yyyy-mm}`

`{spent_usd: float, calls: int, cap_usd: float}`. Read before every fallback call, incremented in a
transaction after it. When `spent_usd >= cap_usd`, fallback is skipped and the reply says how many items
were not checked.

## Baseline — `pantry_baseline/current`

`{taken_at, items: map["location__key" -> count]}`. Written after each morning message (FR-010).

## ProcessedUpdate — `pantry_updates/{update_id}`

`{received_at}`. Telegram retry guard; a Firestore TTL policy on `received_at` removes rows after 7 days.

## PendingQuestion — `pantry_pending/{chat_id}`

`{kind: "new_item", snapshot_id, created_at, entries: [[name, count, "set" | "add", suggested_key | ""]]}`.
One question covers every unknown name in a message (Story 2, scenario 3). A name close to a known item
(typo, plural) carries a suggestion: "yes" applies the suggestion and creates the rest, "new" creates all,
"no" cancels. Expires after 10 minutes.
