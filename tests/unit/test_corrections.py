"""Correction service: target snapshot, kinds, old and new counts, uncertain cleared (FR-007, FR-008)."""

from pantry.domain.corrections import CorrectionService
from pantry.domain.models import InventoryEntry, Location, Snapshot, SnapshotItem
from tests.fakes import FakeClock, InMemoryStore

F = Location.FRIDGE


def setup():
    store, clock = InMemoryStore(), FakeClock()
    now = clock.now()
    a = Snapshot(
        "a", F, now, now, items={"eggs": SnapshotItem(6, 0.8, False, "detector")}, reply_message_ids=[10]
    )
    clock.advance(600)
    b = Snapshot("b", Location.FREEZER, clock.now(), clock.now(), reply_message_ids=[20])
    store.save_snapshot(a)
    store.save_snapshot(b)
    store.upsert_inventory(InventoryEntry(F, "eggs", 6, True, now, "a"))
    return CorrectionService(store, clock), store


def test_target_is_the_replied_snapshot_else_latest():
    svc, _ = setup()
    assert svc.target(10).id == "a"
    assert svc.target(None).id == "b"
    assert svc.target(999).id == "b"


def test_set_count_records_old_and_new_and_clears_uncertain():
    svc, store = setup()
    correction, entry = svc.set_count(store.get_snapshot("a"), "eggs", 4, "ביצים 4")
    assert (correction.kind, correction.old_count, correction.new_count) == ("count", 6, 4)
    assert entry.count == 4 and not entry.uncertain


def test_kinds_follow_detection():
    svc, store = setup()
    snap = store.get_snapshot("a")
    assert svc.set_count(snap, "eggs", 0, "אין ביצים")[0].kind == "false"
    assert svc.set_count(snap, "milk", 2, "חלב 2")[0].kind == "missed"
    assert svc.add(snap, "hummus", 1, "להוסיף חומוס")[0].kind == "missed"


def test_add_adds_to_existing_count():
    svc, store = setup()
    _, entry = svc.add(store.get_snapshot("a"), "eggs", 2, "להוסיף ביצים 2")
    assert entry.count == 8


def test_confirm_keeps_count_and_clears_uncertain():
    svc, store = setup()
    correction, entry = svc.confirm(store.get_snapshot("a"), "eggs")
    assert correction.kind == "confirm" and correction.old_count == correction.new_count == 6
    assert not entry.uncertain


def test_correction_applies_to_target_snapshot_location():
    svc, store = setup()
    svc.add(store.get_snapshot("b"), "chicken", 1, "להוסיף עוף")
    assert [e.location for e in store.get_inventory() if e.key == "chicken"] == [Location.FREEZER]
