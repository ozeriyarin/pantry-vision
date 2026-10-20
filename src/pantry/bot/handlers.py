"""Photo, query and done flows. Corrections and callbacks arrive with User Story 2."""

import time
from uuid import uuid4

from pantry.bot import texts
from pantry.bot.commands import Done, Has, Query, parse_location, parse_text
from pantry.bot.updates import Update
from pantry.config import Settings
from pantry.detection.fallback import Fallback
from pantry.detection.pipeline import Pipeline
from pantry.domain.items import ItemCatalog
from pantry.domain.models import Location, RunRecord, Snapshot, SnapshotPhoto
from pantry.domain.snapshot import SessionService
from pantry.ports import BlobStore, Clock, Detector, Store, TelegramClient, Verifier

_cold = {"first": True}


class Bot:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        telegram: TelegramClient,
        blob: BlobStore,
        detector: Detector,
        verifier: Verifier,
        clock: Clock,
    ):
        self._store, self._telegram, self._blob, self._clock = store, telegram, blob, clock
        self._detector = detector
        fallback = Fallback(verifier, store, clock, settings.fallback, settings.crop)
        self._pipeline = Pipeline(detector, fallback, settings)
        self._sessions = SessionService(store, clock, settings.session_window_s)

    def _catalog(self) -> ItemCatalog:
        return ItemCatalog(self._store.list_item_types())

    def handle(self, update: Update) -> None:
        if update.callback:
            self._telegram.answer_callback(update.callback.id)
        elif update.photo_file_id:
            self._photo(update)
        elif update.text is not None:
            self._text(update)

    # Photos

    def _photo(self, update: Update) -> None:
        cold, _cold["first"] = _cold["first"], False
        start = time.perf_counter()
        now = self._clock.now()
        catalog = self._catalog()
        data = self._telegram.download_file(update.photo_file_id)
        blob_path = self._blob.put_photo(data, now)
        result = self._pipeline.run(data, catalog.keys())
        if result.status == "unclear":
            self._telegram.send_message(update.chat_id, texts.unclear_photo())
            return
        if result.status == "empty":
            self._telegram.send_message(update.chat_id, texts.no_food())
            return

        location = parse_location(update.caption)
        if location is None and update.media_group_id:
            group = self._sessions.session_for_group(update.media_group_id)
            location = group.location if group else None
        location = location or Location.FRIDGE

        photo = SnapshotPhoto(blob_path, update.photo_file_id, result.detections)
        snap = self._sessions.add_photo(location, update.media_group_id, photo, result.items)
        text, buttons = self._photo_reply(snap, catalog, result.skipped)
        message_id = self._telegram.send_message(update.chat_id, text, buttons=buttons or None)
        self._sessions.add_reply(snap, message_id)

        scores: dict[str, list[float]] = {}
        for d in result.detections:
            scores.setdefault(d.key, []).append(round(d.score, 4))
        self._store.add_run(
            RunRecord(
                id=uuid4().hex,
                snapshot_id=snap.id,
                location=location,
                detector_model=self._detector.model_name,
                counts={k: v.count for k, v in result.items.items()},
                scores=scores,
                uncertain_count=sum(1 for v in result.items.values() if v.uncertain),
                fallback_calls=result.fallback_calls,
                fallback_skipped=result.skipped,
                fallback_cost_usd=result.cost_usd,
                latency_ms=int((time.perf_counter() - start) * 1000),
                cold_start=cold,
                created_at=now,
            )
        )

    def _photo_reply(self, snap: Snapshot, catalog: ItemCatalog, skipped: int):
        lines, buttons = [], []
        for key, item in sorted(snap.items.items(), key=lambda kv: self._name(catalog, kv[0])):
            name = self._name(catalog, key)
            lines.append(texts.item_line(name, item.count, item.uncertain))
            if item.uncertain:
                buttons.append(
                    [
                        (f"{texts.CONFIRM} {name}", f"confirm:{snap.id}:{key}"),
                        (f"{texts.REMOVE} {name}", f"remove:{snap.id}:{key}"),
                    ]
                )
        return texts.photo_reply(snap.location, lines, skipped), buttons

    @staticmethod
    def _name(catalog: ItemCatalog, key: str) -> str:
        item = catalog.get(key)
        return item.name_he if item else key

    # Text

    def _text(self, update: Update) -> None:
        intent = parse_text(update.text or "")
        catalog = self._catalog()
        if isinstance(intent, Query):
            reply = self._inventory(catalog, intent.location)
        elif isinstance(intent, Has):
            reply = self._has(catalog, intent.name)
        elif isinstance(intent, Done):
            snap, zeroed = self._sessions.close(None)
            if snap is None:
                reply = texts.no_open_session()
            else:
                reply = texts.session_closed(snap.location, [self._name(catalog, k) for k in zeroed])
        else:
            reply = texts.not_understood()
        self._telegram.send_message(update.chat_id, reply)

    def _inventory(self, catalog: ItemCatalog, location: Location | None) -> str:
        groups: dict[Location, list[str]] = {}
        for loc in [location] if location else list(Location):
            entries = [e for e in self._store.get_inventory(loc) if e.count > 0]
            entries.sort(key=lambda e: self._name(catalog, e.key))
            groups[loc] = [texts.item_line(self._name(catalog, e.key), e.count, e.uncertain) for e in entries]
        return texts.inventory(groups)

    def _has(self, catalog: ItemCatalog, name: str) -> str:
        item = catalog.resolve(name)
        if item is None:
            return texts.no_item(name)
        for entry in self._store.get_inventory():
            if entry.key == item.key and entry.count > 0:
                return texts.has_item(item.name_he, entry.count, entry.location)
        return texts.no_item(item.name_he)
