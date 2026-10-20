"""Owner corrections update the inventory at once and are kept as labels (FR-007, FR-008)."""

from uuid import uuid4

from pantry.domain.models import Correction, InventoryEntry, Location, Snapshot
from pantry.ports import Clock, Store


class CorrectionService:
    def __init__(self, store: Store, clock: Clock):
        self._store, self._clock = store, clock

    def target(self, reply_to_message_id: int | None) -> Snapshot | None:
        """The replied-to snapshot, else the most recent one of any location."""
        if reply_to_message_id:
            snap = self._store.snapshot_for_reply(reply_to_message_id)
            if snap:
                return snap
        return self._store.latest_snapshot()

    def _current(self, location: Location, key: str) -> InventoryEntry | None:
        return next((e for e in self._store.get_inventory(location) if e.key == key), None)

    def _apply(self, snap: Snapshot | None, key: str, new_count: int, kind: str, text: str):
        location = snap.location if snap else Location.FRIDGE
        snapshot_id = snap.id if snap else ""
        now = self._clock.now()
        current = self._current(location, key)
        old = current.count if current else 0
        entry = InventoryEntry(location, key, max(0, new_count), False, now, snapshot_id or "")
        self._store.upsert_inventory(entry)
        correction = Correction(uuid4().hex, snapshot_id, key, kind, old, entry.count, now, text)
        self._store.add_correction(correction)
        return correction, entry

    @staticmethod
    def _detected(snap: Snapshot | None, key: str) -> bool:
        return bool(snap) and key in snap.items

    def set_count(self, snap: Snapshot | None, key: str, count: int, text: str):
        detected = self._detected(snap, key)
        if detected and count == 0:
            kind = "false"
        elif not detected and count > 0:
            kind = "missed"
        else:
            kind = "count"
        return self._apply(snap, key, count, kind, text)

    def add(self, snap: Snapshot | None, key: str, count: int, text: str):
        location = snap.location if snap else Location.FRIDGE
        current = self._current(location, key)
        kind = "count" if self._detected(snap, key) else "missed"
        return self._apply(snap, key, (current.count if current else 0) + count, kind, text)

    def confirm(self, snap: Snapshot, key: str):
        current = self._current(snap.location, key)
        return self._apply(snap, key, current.count if current else 1, "confirm", "✓")
