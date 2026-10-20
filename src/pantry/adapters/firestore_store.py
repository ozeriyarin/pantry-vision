"""Store on Firestore, collections prefixed pantry_ (research R9). Converters are pure and unit-tested."""

from dataclasses import asdict, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

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
    SnapshotItem,
    SnapshotPhoto,
    inventory_id,
)


def plain(value: Any) -> Any:
    if is_dataclass(value):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [plain(v) for v in value]
    return value


def _detection(d: dict) -> Detection:
    fb = d.get("fallback")
    return Detection(d["key"], tuple(d["box"]), d["score"], FallbackResult(**fb) if fb else None)


def snapshot_from(d: dict) -> Snapshot:
    return Snapshot(
        id=d["id"],
        location=Location(d["location"]),
        opened_at=d["opened_at"],
        last_photo_at=d["last_photo_at"],
        media_group_id=d.get("media_group_id"),
        photos=[
            SnapshotPhoto(p["blob_path"], p["telegram_file_id"], [_detection(x) for x in p["detections"]])
            for p in d.get("photos", [])
        ],
        items={k: SnapshotItem(**v) for k, v in d.get("items", {}).items()},
        closed_by=d.get("closed_by"),
        full=d.get("full", False),
        reply_message_ids=list(d.get("reply_message_ids", [])),
    )


def item_type_from(d: dict) -> ItemType:
    hint = d.get("location_hint")
    return ItemType(
        key=d["key"],
        name_he=d["name_he"],
        aliases=tuple(d.get("aliases", [])),
        prompt=d.get("prompt", ""),
        location_hint=Location(hint) if hint else None,
        added_by=d.get("added_by", "seed"),
    )


def inventory_from(d: dict) -> InventoryEntry:
    return InventoryEntry(**{**d, "location": Location(d["location"])})


class FirestoreStore:
    def __init__(self, client=None, prefix: str = "pantry_"):
        from google.cloud import firestore

        self._firestore = firestore
        self._db = client or firestore.Client()
        self._prefix = prefix

    def _col(self, name: str):
        return self._db.collection(f"{self._prefix}{name}")

    def mark_update_seen(self, update_id: int, now: datetime) -> bool:
        from google.api_core.exceptions import AlreadyExists

        try:
            self._col("updates").document(str(update_id)).create({"received_at": now})
            return True
        except AlreadyExists:
            return False

    def list_item_types(self) -> list[ItemType]:
        return [item_type_from(doc.to_dict()) for doc in self._col("item_types").stream()]

    def upsert_item_type(self, item: ItemType) -> None:
        self._col("item_types").document(item.key).set(plain(item))

    def save_snapshot(self, snapshot: Snapshot) -> None:
        self._col("snapshots").document(snapshot.id).set(plain(snapshot))

    def get_snapshot(self, snapshot_id: str) -> Snapshot | None:
        doc = self._col("snapshots").document(snapshot_id).get()
        return snapshot_from(doc.to_dict()) if doc.exists else None

    def latest_snapshot(self, location: Location | None = None) -> Snapshot | None:
        query = self._col("snapshots")
        if location:
            query = query.where(filter=self._firestore.FieldFilter("location", "==", location.value))
        docs = list(query.order_by("last_photo_at", direction="DESCENDING").limit(1).stream())
        return snapshot_from(docs[0].to_dict()) if docs else None

    def snapshot_for_reply(self, message_id: int) -> Snapshot | None:
        flt = self._firestore.FieldFilter("reply_message_ids", "array_contains", message_id)
        docs = list(self._col("snapshots").where(filter=flt).limit(1).stream())
        return snapshot_from(docs[0].to_dict()) if docs else None

    def get_inventory(self, location: Location | None = None) -> list[InventoryEntry]:
        query = self._col("inventory")
        if location:
            query = query.where(filter=self._firestore.FieldFilter("location", "==", location.value))
        return [inventory_from(doc.to_dict()) for doc in query.stream()]

    def upsert_inventory(self, entry: InventoryEntry) -> None:
        self._col("inventory").document(inventory_id(entry.location, entry.key)).set(plain(entry))

    def add_correction(self, correction: Correction) -> None:
        self._col("corrections").document(correction.id).set(plain(correction))

    def add_run(self, run: RunRecord) -> None:
        self._col("runs").document(run.id).set(plain(run))

    def get_budget(self, month: str, cap_usd: float) -> Budget:
        doc = self._col("budget").document(month).get()
        data = doc.to_dict() if doc.exists else {}
        return Budget(month, data.get("spent_usd", 0.0), data.get("calls", 0), cap_usd)

    def add_spend(self, month: str, usd: float, cap_usd: float) -> Budget:
        ref = self._col("budget").document(month)

        @self._firestore.transactional
        def apply(transaction) -> Budget:
            snap = ref.get(transaction=transaction)
            data = snap.to_dict() if snap.exists else {}
            budget = Budget(month, data.get("spent_usd", 0.0) + usd, data.get("calls", 0) + 1, cap_usd)
            transaction.set(ref, asdict(budget))
            return budget

        return apply(self._db.transaction())

    def get_baseline(self) -> Baseline | None:
        doc = self._col("baseline").document("current").get()
        return Baseline(**doc.to_dict()) if doc.exists else None

    def save_baseline(self, baseline: Baseline) -> None:
        self._col("baseline").document("current").set(plain(baseline))

    def get_pending(self, chat_id: int) -> PendingQuestion | None:
        doc = self._col("pending").document(str(chat_id)).get()
        return PendingQuestion(**doc.to_dict()) if doc.exists else None

    def set_pending(self, question: PendingQuestion) -> None:
        self._col("pending").document(str(question.chat_id)).set(plain(question))

    def clear_pending(self, chat_id: int) -> None:
        self._col("pending").document(str(chat_id)).delete()
