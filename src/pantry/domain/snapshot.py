"""Photo sessions (FR-005, research R5): merge by highest count, upsert seen items, full or partial close."""

from datetime import datetime
from uuid import uuid4

from pantry.domain.models import InventoryEntry, Location, Snapshot, SnapshotItem, SnapshotPhoto
from pantry.ports import Clock, Store


def _merge(old: SnapshotItem, new: SnapshotItem) -> SnapshotItem:
    if new.count > old.count:
        return SnapshotItem(new.count, max(old.score, new.score), new.uncertain, new.source)
    if new.count < old.count:
        return SnapshotItem(old.count, max(old.score, new.score), old.uncertain, old.source)
    return SnapshotItem(old.count, max(old.score, new.score), old.uncertain and new.uncertain, old.source)


class SessionService:
    def __init__(self, store: Store, clock: Clock, window_s: int):
        self._store, self._clock, self._window = store, clock, window_s

    def _is_open(self, snap: Snapshot | None, now: datetime) -> bool:
        return (
            bool(snap)
            and snap.closed_by is None
            and (now - snap.last_photo_at).total_seconds() <= self._window
        )

    def _expire(self, snap: Snapshot | None, now: datetime) -> None:
        if snap and snap.closed_by is None and not self._is_open(snap, now):
            snap.closed_by = "timeout"
            self._store.save_snapshot(snap)

    def open_session(self, location: Location | None = None) -> Snapshot | None:
        now = self._clock.now()
        snap = self._store.latest_snapshot(location)
        if self._is_open(snap, now):
            return snap
        self._expire(snap, now)
        return None

    def session_for_group(self, media_group_id: str) -> Snapshot | None:
        snap = self._store.latest_snapshot()
        if snap and snap.closed_by is None and snap.media_group_id == media_group_id:
            return snap
        return None

    def add_photo(
        self,
        location: Location,
        media_group_id: str | None,
        photo: SnapshotPhoto,
        items: dict[str, SnapshotItem],
    ) -> Snapshot:
        now = self._clock.now()
        snap = self.session_for_group(media_group_id) if media_group_id else None
        if snap is None or snap.location != location:
            snap = self.open_session(location)
        if snap is None:
            snap = Snapshot(uuid4().hex[:12], location, now, now, media_group_id)
        snap.last_photo_at = now
        snap.media_group_id = snap.media_group_id or media_group_id
        snap.photos.append(photo)
        for key, new in items.items():
            snap.items[key] = _merge(snap.items[key], new) if key in snap.items else new
        for key in items:
            merged = snap.items[key]
            self._store.upsert_inventory(
                InventoryEntry(location, key, merged.count, merged.uncertain, now, snap.id)
            )
        self._store.save_snapshot(snap)
        return snap

    def close(self, location: Location | None) -> tuple[Snapshot | None, list[str]]:
        """Close the open session as a full view; unseen items of its location go to 0."""
        snap = self.open_session(location)
        if snap is None:
            return None, []
        snap.closed_by, snap.full = "done", True
        zeroed = []
        for entry in self._store.get_inventory(snap.location):
            if entry.count > 0 and entry.key not in snap.items:
                entry.count, entry.uncertain, entry.snapshot_id = 0, False, snap.id
                self._store.upsert_inventory(entry)
                zeroed.append(entry.key)
        self._store.save_snapshot(snap)
        return snap, sorted(zeroed)

    def add_reply(self, snap: Snapshot, message_id: int) -> None:
        snap.reply_message_ids.append(message_id)
        self._store.save_snapshot(snap)
