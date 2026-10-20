"""In-memory fakes for every port, so pytest runs offline with no keys (Principle VI)."""

import copy
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

from pantry.domain.models import (
    Baseline,
    Budget,
    Correction,
    Detection,
    FallbackResult,
    InventoryEntry,
    ItemType,
    Location,
    PendingQuestion,
    RunRecord,
    Snapshot,
    inventory_id,
)
from pantry.ports import Buttons


@dataclass
class SentMessage:
    chat_id: int
    text: str
    buttons: Buttons | None
    reply_to: int | None
    message_id: int


@dataclass
class FakeTelegram:
    sent: list[SentMessage] = field(default_factory=list)
    answered: list[tuple[str, str | None]] = field(default_factory=list)
    markups: list[tuple[int, int, Buttons | None]] = field(default_factory=list)
    files: dict[str, bytes] = field(default_factory=dict)
    _next_id: int = 1000

    def send_message(self, chat_id, text, buttons=None, reply_to=None) -> int:
        self._next_id += 1
        self.sent.append(SentMessage(chat_id, text, buttons, reply_to, self._next_id))
        return self._next_id

    def answer_callback(self, callback_id, text=None) -> None:
        self.answered.append((callback_id, text))

    def set_buttons(self, chat_id, message_id, buttons) -> None:
        self.markups.append((chat_id, message_id, buttons))

    def download_file(self, file_id) -> bytes:
        return self.files[file_id]


@dataclass
class FakeBlob:
    stored: dict[str, bytes] = field(default_factory=dict)

    def put_photo(self, data: bytes, now: datetime) -> str:
        path = f"photos/{now:%Y/%m/%d}/{len(self.stored):04d}.jpg"
        self.stored[path] = data
        return path


@dataclass
class FakeDetector:
    """Returns scripted detections keyed by the photo bytes."""

    script: dict[bytes, list[Detection]] = field(default_factory=dict)
    model_name: str = "fake-detector"

    def detect(self, image: bytes) -> list[Detection]:
        return list(self.script.get(image, []))


@dataclass
class FakeVerifier:
    """Answers in order; an Exception instance in the queue is raised."""

    answers: list = field(default_factory=list)
    calls: int = 0

    def verify(self, crop_jpeg: bytes, keys: Sequence[str]) -> FallbackResult:
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


@dataclass
class FakeClock:
    current: datetime = field(default_factory=lambda: datetime(2026, 10, 20, 9, 0, tzinfo=UTC))

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


class InMemoryStore:
    def __init__(self, item_types: list[ItemType] | None = None):
        self.calls: list[str] = []
        self.updates: dict[int, datetime] = {}
        self.item_types = {i.key: i for i in item_types or []}
        self.snapshots: dict[str, Snapshot] = {}
        self.inventory: dict[str, InventoryEntry] = {}
        self.corrections: list[Correction] = []
        self.runs: list[RunRecord] = []
        self.budgets: dict[str, Budget] = {}
        self.baseline: Baseline | None = None
        self.pending: dict[int, PendingQuestion] = {}

    def _log(self, name: str) -> None:
        self.calls.append(name)

    def mark_update_seen(self, update_id, now) -> bool:
        self._log("mark_update_seen")
        if update_id in self.updates:
            return False
        self.updates[update_id] = now
        return True

    def list_item_types(self):
        self._log("list_item_types")
        return list(self.item_types.values())

    def upsert_item_type(self, item):
        self._log("upsert_item_type")
        self.item_types[item.key] = item

    def save_snapshot(self, snapshot):
        self._log("save_snapshot")
        self.snapshots[snapshot.id] = copy.deepcopy(snapshot)

    def get_snapshot(self, snapshot_id):
        self._log("get_snapshot")
        s = self.snapshots.get(snapshot_id)
        return copy.deepcopy(s) if s else None

    def latest_snapshot(self, location: Location | None = None):
        self._log("latest_snapshot")
        found = [s for s in self.snapshots.values() if location is None or s.location == location]
        return copy.deepcopy(max(found, key=lambda s: s.last_photo_at)) if found else None

    def snapshot_for_reply(self, message_id):
        self._log("snapshot_for_reply")
        for s in self.snapshots.values():
            if message_id in s.reply_message_ids:
                return copy.deepcopy(s)
        return None

    def get_inventory(self, location=None):
        self._log("get_inventory")
        return [replace(e) for e in self.inventory.values() if location is None or e.location == location]

    def upsert_inventory(self, entry):
        self._log("upsert_inventory")
        self.inventory[inventory_id(entry.location, entry.key)] = replace(entry)

    def add_correction(self, correction):
        self._log("add_correction")
        self.corrections.append(correction)

    def add_run(self, run):
        self._log("add_run")
        self.runs.append(run)

    def get_budget(self, month, cap_usd):
        self._log("get_budget")
        return self.budgets.get(month, Budget(month, 0.0, 0, cap_usd))

    def add_spend(self, month, usd, cap_usd):
        self._log("add_spend")
        b = self.get_budget(month, cap_usd)
        self.budgets[month] = Budget(month, b.spent_usd + usd, b.calls + 1, cap_usd)
        return self.budgets[month]

    def get_baseline(self):
        self._log("get_baseline")
        return self.baseline

    def save_baseline(self, baseline):
        self._log("save_baseline")
        self.baseline = baseline

    def get_pending(self, chat_id):
        self._log("get_pending")
        return self.pending.get(chat_id)

    def set_pending(self, question):
        self._log("set_pending")
        self.pending[question.chat_id] = question

    def clear_pending(self, chat_id):
        self._log("clear_pending")
        self.pending.pop(chat_id, None)
