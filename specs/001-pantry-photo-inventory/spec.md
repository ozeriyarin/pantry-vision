# Feature Specification: Pantry photo inventory

**Feature Branch**: `001-pantry-photo-inventory`
**Created**: 2026-10-20
**Status**: Shipped (bot and pipeline live since 2026-10-20; the labelled-photo eval and the fine-tune were parked by the owner on 2026-10-25, see tasks T050/T051)
**Input**: User description: "A Telegram bot in Hebrew for one owner: send a photo of the fridge, freezer or pantry, get back the items it recognised with counts, correct mistakes, keep a running inventory per location, and receive a daily morning message about items expiring soon or running low. Recipes and barcode scanning are out of scope. Runs in the cloud, not on the owner's machine, under 10 USD a month."

## Clarifications

### Session 2026-10-20

- Q: Is expiry tracking in v1? → A: No. The morning message lists run-out items only; expiry is a later spec.
- Q: How does the owner name the location of a photo? → A: A caption word (מקרר, מקפיא, מזווה); no caption means fridge.
- Q: Does an uncertain item enter the inventory? → A: Yes, marked uncertain; a correction clears the mark.
- Q: Is the 80% count accuracy a launch gate for the zero-shot detector? → A: No. It is the fine-tuned target; zero-shot is a reported baseline.
- Q: Does the 15-second reply limit include cold starts? → A: No. Cold starts are measured separately; no paid always-on instance.
- Q: Can the owner add locations beyond fridge, freezer and pantry? → A: Yes, from the chat ("מיקום חדש: מקרר שני"); the three built-in ones stay the defaults.
- Q: How are partial and overlapping photos handled? → A: Photos of one location within 5 minutes form a session, merged by the highest count per item. "סיימתי" marks the session as a full view that replaces the location's inventory; a session that times out updates only the items it saw.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Photo to inventory (Priority: P1)

The owner opens the fridge, takes a photo and sends it to the bot with the location (fridge, freezer or pantry; fridge by default). Within seconds the bot replies in Hebrew with the items it recognised and how many of each, marking the ones it is unsure about. The inventory for that location is replaced by what the photo shows, and the owner can ask "מה יש לי?" or "יש ביצים?" to get the current list or a yes/no with the count.

**Why this priority**: It is the whole product in one loop. Without it nothing else has data.

**Independent Test**: Send a known photo; the reply lists the expected items and counts, and the inventory query returns the same list.

**Acceptance Scenarios**:

1. **Given** an empty fridge inventory, **When** the owner sends a fridge photo containing 6 eggs and 2 milk cartons, **Then** the bot replies within 15 seconds listing "ביצים ×6" and "חלב ×2", and "מה יש לי במקרר?" returns the same items.
2. **Given** a photo where one item is recognised with low certainty, **When** the reply is sent, **Then** that item is marked as uncertain (for example "?") rather than presented as fact.
3. **Given** a photo with no recognisable food items, **When** it is sent, **Then** the bot says it found nothing and leaves the inventory unchanged.
4. **Given** a message from any chat that is not the owner's, **When** it arrives, **Then** the bot does not process it and does not reply with any inventory data.
5. **Given** milk in the fridge inventory, **When** the owner sends a door photo without milk and does not send "סיימתי", **Then** milk keeps its count.
6. **Given** an open fridge session, **When** the owner sends "סיימתי", **Then** fridge items not seen in the session are set to 0 and the bot lists them.

---

### User Story 2 - Correct the bot (Priority: P2)

The owner sees a wrong item or count and fixes it with a short Hebrew reply ("אין חלב", "ביצים 4", "להוסיף חומוס") or one tap on a suggested fix. The inventory updates immediately, and the correction is kept, together with the photo it applies to, as a labelled example for improving recognition later.

**Why this priority**: Recognition will make mistakes; without corrections the inventory drifts and the owner stops trusting it. Corrections are also the training data source.

**Independent Test**: After a photo reply, send "ביצים 4"; the inventory shows 4 eggs and a correction record exists linking the photo to the corrected count.

**Acceptance Scenarios**:

1. **Given** the bot reported "ביצים ×6", **When** the owner replies "ביצים 4", **Then** the inventory shows 4 eggs and the bot confirms the change.
2. **Given** the bot missed hummus, **When** the owner replies "להוסיף חומוס", **Then** hummus ×1 is added and recorded as a missed detection for that photo.
3. **Given** a correction naming an item not in the known item list, **When** it is sent, **Then** the bot asks whether to add it as a new item type instead of guessing.

---

### User Story 3 - Morning heads-up (Priority: P3)

Every morning at a fixed time the owner gets one short Hebrew message listing items that have run out since the previous morning, so the shopping list is ready before leaving the house. Expiry dates are out of scope for this version.

**Why this priority**: It turns the inventory into something that saves shopping trips, but it needs Stories 1 and 2 to have data.

**Independent Test**: Seed yesterday's inventory with milk and today's snapshot without it; the next morning's message lists milk as run out.

**Acceptance Scenarios**:

1. **Given** milk was in the inventory at the previous morning message and the latest snapshot shows none, **When** the morning message is sent, **Then** it lists milk as run out.
2. **Given** nothing ran out since the previous morning, **When** the morning time comes, **Then** the bot sends a one-line "all good" message rather than nothing, so the owner knows it ran.
3. **Given** a partial session that did not show milk, **When** the morning message is sent, **Then** milk is not listed as run out.

### Edge Cases

- A blurry or dark photo: the bot says it could not see clearly and suggests retaking it; inventory unchanged.
- A photo of part of a location: updates only the items it shows; nothing is set to 0 until the owner sends "סיימתי" or corrects it.
- Several photos of the same location within the session window (shelf by shelf, possibly overlapping): one snapshot, merged by the highest count per item, not each one replacing the last.
- Packaged items that look alike (different yogurt brands): grouped under one item type in v1.
- The second recognition step is unavailable or its monthly budget is exhausted: the bot replies with what the first step found and says some items may be missing; it never fails silently.
- Hebrew and English item names in corrections ("milk" / "חלב") map to the same item type.
- A photo arrives while the previous one is still being processed: processed in order, each gets its own reply.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a photo from the owner's Telegram chat with an optional location given as a caption word (מקרר, מקפיא, מזווה; no caption means fridge) and reply in Hebrew with recognised items and counts.
- **FR-002**: System MUST serve only an allow-listed set of chat ids and ignore all others without revealing data.
- **FR-003**: System MUST mark items recognised below a configurable certainty threshold as uncertain in the reply; uncertain items enter the inventory with an uncertain mark that a correction clears.
- **FR-004**: System MUST re-check uncertain items with a second, more capable recognition step, limited by a monthly spending cap, and record the cost of every such check.
- **FR-005**: System MUST keep a current inventory per location. Photos of one location within a configurable session window (default 5 minutes) form one snapshot, merged by the highest count per item. A snapshot the owner closes with "סיימתי" replaces that location's inventory; a snapshot that times out updates only the items it saw.
- **FR-006**: Users MUST be able to query the inventory in Hebrew ("מה יש לי", "יש <item>?", per location).
- **FR-007**: Users MUST be able to correct counts, remove items and add missed items with short Hebrew or English replies, and the inventory MUST update immediately.
- **FR-008**: System MUST store each correction with a reference to its photo as a labelled example for later evaluation and training.
- **FR-009**: System MUST maintain a known item list (about 30 Hebrew item types with English aliases), editable without a code change.
- **FR-010**: System MUST send one morning message per day at a configured time listing items run out since the previous morning message, or a one-line all-good message.
- **FR-011**: *Removed: expiry tracking is deferred to a later spec.*
- **FR-012**: System MUST delete stored photos 30 days after upload and MUST NOT log or commit photo contents.
- **FR-013**: System MUST write a record per processed photo with item counts, certainty levels, second-step calls, cost and latency, and no image data.
- **FR-014**: System MUST run entirely in the cloud and keep working when the owner's computer is off.

### Key Entities

- **Item type**: a kind of food the owner keeps (Hebrew name, English aliases, location hint).
- **Snapshot**: one or more photos of one location within the session window, closed as full ("סיימתי") or partial (timeout); has a time, location and detected items with counts and certainty.
- **Inventory entry**: the current count of an item type in a location and the time it was last seen.
- **Correction**: an owner fix tied to a snapshot (item type, old count, new count, kind: count, missed or false); the source of labelled examples.
- **Run record**: per-photo counts, certainty, second-step calls, cost and latency; no images.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The owner gets a reply to a photo within 15 seconds in at least 95% of cases while the service is warm; cold-start replies are measured and reported separately, with no paid always-on instance.
- **SC-002**: On the owner's labelled evaluation photos, counted items match the true counts for at least 80% of item occurrences with the fine-tuned detector, published with per-item precision and recall; the zero-shot detector is reported as a baseline with no pass mark.
- **SC-003**: After two weeks of use, the owner needs on average no more than two corrections per photo.
- **SC-004**: Total monthly running cost stays under 10 USD, and each month's cost is visible from the run records.
- **SC-005**: The morning message arrives every day of a two-week trial without the owner's computer being on.

## Assumptions

- Single owner; family sharing, recipes, barcode scanning and expiry tracking are later features.
- Photos are taken with a phone in normal kitchen light; the owner retakes a photo when asked.
- About 30 item types cover most of what the owner keeps; similar brands are grouped in v1.
- The morning message time defaults to 07:30 Asia/Jerusalem.
- The owner supplies about 200 photos over two weeks and labels about 150 of them for the evaluation set; photos are never committed to the repository.
- The existing Google Cloud project with billing is reused; a new Telegram bot and a dedicated, capped Anthropic key are created for this project.
