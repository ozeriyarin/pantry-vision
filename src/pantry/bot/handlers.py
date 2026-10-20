"""Photo, query, correction, button and done flows."""

import logging
import time
from uuid import uuid4

from pantry.bot import texts
from pantry.bot.commands import (
    Add,
    Done,
    Has,
    Query,
    Remove,
    SetCount,
    parse_location,
    parse_text,
    split_lines,
)
from pantry.bot.updates import Update
from pantry.config import Settings
from pantry.detection.fallback import Fallback
from pantry.detection.pipeline import Pipeline
from pantry.domain.corrections import CorrectionService
from pantry.domain.items import ItemCatalog, normalise
from pantry.domain.models import ItemType, Location, PendingQuestion, RunRecord, Snapshot, SnapshotPhoto
from pantry.domain.morning import MorningService
from pantry.domain.snapshot import SessionService
from pantry.ports import BlobStore, Clock, Detector, Store, TelegramClient, Verifier

log = logging.getLogger("pantry")
_cold = {"first": True}
MAX_NAME = 40


def valid_new_name(name: str) -> bool:
    return 0 < len(normalise(name)) <= MAX_NAME


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
        self._corrections = CorrectionService(store, clock)
        self._pending_ttl_s = settings.pending_ttl_min * 60
        self._morning = MorningService(store, clock, settings.morning_tz)
        self._owners = sorted(settings.allowed_chat_ids)

    def _catalog(self) -> ItemCatalog:
        catalog = ItemCatalog(self._store.list_item_types(), strict=False)
        if catalog.skipped:
            log.warning("item types skipped for name clashes: %s", ", ".join(catalog.skipped))
        return catalog

    def handle(self, update: Update) -> None:
        if update.callback:
            self._callback(update)
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
        text = texts.photo_reply(snap.location, self._lines(snap, catalog), result.skipped)
        buttons = self._uncertain_buttons(snap, catalog)
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

    def _lines(self, snap: Snapshot, catalog: ItemCatalog) -> list[str]:
        items = sorted(snap.items.items(), key=lambda kv: self._name(catalog, kv[0]))
        return [texts.item_line(self._name(catalog, k), v.count, v.uncertain) for k, v in items]

    def _uncertain_buttons(self, snap: Snapshot, catalog: ItemCatalog) -> list:
        """One ✓/✗ row per item of the snapshot that is still uncertain in the inventory."""
        uncertain = {e.key for e in self._store.get_inventory(snap.location) if e.uncertain}
        rows = []
        for key in sorted(snap.items, key=lambda k: self._name(catalog, k)):
            if key in uncertain and snap.items[key].uncertain:
                name = self._name(catalog, key)
                rows.append(
                    [
                        (f"{texts.CONFIRM} {name}", f"confirm:{snap.id}:{key}"),
                        (f"{texts.REMOVE} {name}", f"remove:{snap.id}:{key}"),
                    ]
                )
        return rows

    @staticmethod
    def _name(catalog: ItemCatalog, key: str) -> str:
        item = catalog.get(key)
        return item.name_he if item else key

    # Text

    def _text(self, update: Update) -> None:
        catalog = self._catalog()
        segments = split_lines(update.text or "")
        if len(segments) > 1:
            reply, buttons = self._correct_many(update, catalog, segments)
            self._telegram.send_message(update.chat_id, reply, buttons=buttons)
            return
        intent = parse_text(update.text or "")
        if isinstance(intent, Query):
            reply = self._inventory(catalog, intent.location)
        elif isinstance(intent, Has):
            reply = self._has(catalog, intent.name)
        elif isinstance(intent, SetCount | Remove | Add):
            reply, buttons = self._correct(update, catalog, intent)
            self._telegram.send_message(update.chat_id, reply, buttons=buttons)
            return
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

    # Corrections

    def _correct(self, update: Update, catalog: ItemCatalog, intent: SetCount | Remove | Add):
        if not valid_new_name(intent.name):
            return texts.not_understood(), None
        item = catalog.resolve(intent.name)
        snap = self._corrections.target(update.reply_to_message_id)
        text = update.text or ""
        if item is None:
            if isinstance(intent, Remove):
                return texts.no_item(intent.name), None
            question = PendingQuestion(
                update.chat_id,
                "new_item",
                intent.name,
                snap.id if snap else None,
                intent.count,
                self._clock.now(),
            )
            self._store.set_pending(question)
            return texts.unknown_item(intent.name), [[(texts.YES, "newitem:yes"), (texts.NO, "newitem:no")]]
        entry = self._apply(snap, item.key, intent, text)
        return texts.updated(item.name_he, entry.count), None

    def _apply(self, snap, key: str, intent: SetCount | Remove | Add, text: str):
        if isinstance(intent, Add):
            return self._corrections.add(snap, key, intent.count, text)[1]
        count = 0 if isinstance(intent, Remove) else intent.count
        return self._corrections.set_count(snap, key, count, text)[1]

    def _correct_many(self, update: Update, catalog: ItemCatalog, segments: list[str]):
        """One correction per line or comma; unknown names get a single yes/no question."""
        snap = self._corrections.target(update.reply_to_message_id)
        done, unknown, bad = [], [], []
        for seg in segments:
            intent = parse_text(seg)
            if not isinstance(intent, SetCount | Remove | Add) or not valid_new_name(intent.name):
                bad.append(seg)
                continue
            item = catalog.resolve(intent.name)
            if item is None:
                if isinstance(intent, Remove):
                    done.append(texts.no_item(intent.name))
                elif intent.name.strip() not in [n for n, _ in unknown]:
                    unknown.append((intent.name.strip(), intent.count))
                continue
            entry = self._apply(snap, item.key, intent, seg)
            done.append(texts.item_line(item.name_he, entry.count))
        lines = texts.updated_many(done) + [texts.not_understood_line(b) for b in bad]
        buttons = None
        if unknown:
            (name, count), more = unknown[0], tuple(unknown[1:])
            snap_id = snap.id if snap else None
            question = PendingQuestion(
                update.chat_id, "new_item", name, snap_id, count, self._clock.now(), more
            )
            self._store.set_pending(question)
            lines.append(texts.unknown_items([n for n, _ in unknown]))
            buttons = [[(texts.YES, "newitem:yes"), (texts.NO, "newitem:no")]]
        return "\n".join(lines) or texts.not_understood(), buttons

    # Buttons

    def _callback(self, update: Update) -> None:
        cb = update.callback
        action, _, rest = cb.data.partition(":")
        if action == "newitem":
            self._cosmetic(self._telegram.answer_callback, cb.id)
            if cb.message_id:
                self._cosmetic(self._telegram.set_buttons, update.chat_id, cb.message_id, None)
            self._new_item(update.chat_id, rest == "yes")
            return
        snapshot_id, _, key = rest.partition(":")
        snap = self._store.get_snapshot(snapshot_id) if action in ("confirm", "remove") else None
        catalog = self._catalog()
        if snap is None or not key:
            self._telegram.answer_callback(cb.id, texts.stale_button())
            return
        if action == "confirm":
            _, entry = self._corrections.confirm(snap, key)
        else:
            _, entry = self._corrections.set_count(snap, key, 0, "✗")
        # The correction is saved; the toast and button refresh are cosmetic and must not fail the tap.
        self._cosmetic(
            self._telegram.answer_callback, cb.id, texts.updated(self._name(catalog, key), entry.count)
        )
        if cb.message_id:
            rows = self._uncertain_buttons(snap, catalog)
            self._cosmetic(self._telegram.set_buttons, update.chat_id, cb.message_id, rows or None)

    @staticmethod
    def _cosmetic(call, *args) -> None:
        try:
            call(*args)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "cosmetic telegram call failed: %s", exc if "telegram" in str(exc) else type(exc).__name__
            )

    def _new_item(self, chat_id: int, accepted: bool) -> None:
        pending = self._store.get_pending(chat_id)
        self._store.clear_pending(chat_id)
        now = self._clock.now()
        if pending is None or (now - pending.created_at).total_seconds() > self._pending_ttl_s:
            self._telegram.send_message(chat_id, texts.question_expired())
            return
        if not accepted:
            self._telegram.send_message(chat_id, texts.not_added())
            return
        snap = self._store.get_snapshot(pending.snapshot_id) if pending.snapshot_id else None
        catalog = self._catalog()
        added = []
        for name, count in [(pending.name, pending.count), *pending.more]:
            item = ItemType(key=f"owner_{uuid4().hex[:8]}", name_he=name.strip(), added_by="owner")
            try:
                catalog.add(item)
            except ValueError:
                continue
            self._store.upsert_item_type(item)
            _, entry = self._corrections.add(snap, item.key, count, f"+ {name}")
            added.append((item.name_he, entry.count))
        if not added:
            self._telegram.send_message(chat_id, texts.not_added())
        elif len(added) == 1:
            self._telegram.send_message(chat_id, texts.updated(*added[0]))
        else:
            lines = [texts.item_line(n, c) for n, c in added]
            self._telegram.send_message(chat_id, "\n".join(texts.updated_many(lines)))

    # Morning (Cloud Scheduler)

    def morning(self) -> dict:
        plan = self._morning.plan()
        if plan is None:
            return {"sent": 0, "run_out": 0}
        catalog = self._catalog()
        text = texts.morning([(self._name(catalog, key), loc) for key, loc in plan.run_out])
        for chat_id in self._owners:
            self._telegram.send_message(chat_id, text)
        self._morning.commit(plan)
        return {"sent": len(self._owners), "run_out": len(plan.run_out)}
