"""Photo sessions (research R5): window, media group, highest-count merge, partial vs full close."""

from pantry.domain.models import Location, SnapshotItem, SnapshotPhoto
from pantry.domain.snapshot import SessionService
from tests.fakes import FakeClock, InMemoryStore

F = Location.FRIDGE


def item(count, uncertain=False, score=0.8):
    return SnapshotItem(count, score, uncertain, "detector")


def photo():
    return SnapshotPhoto("photos/x.jpg", "file")


def make():
    store, clock = InMemoryStore(), FakeClock()
    return SessionService(store, clock, window_s=300), store, clock


def test_photos_within_window_share_a_session_and_merge_by_highest_count():
    svc, store, clock = make()
    a = svc.add_photo(F, None, photo(), {"eggs": item(6), "beer": item(1)})
    clock.advance(299)
    b = svc.add_photo(F, None, photo(), {"eggs": item(4), "beer": item(2)})
    assert a.id == b.id
    assert {k: v.count for k, v in b.items.items()} == {"eggs": 6, "beer": 2}
    assert len(b.photos) == 2


def test_photo_after_window_closes_old_session_as_partial():
    svc, store, clock = make()
    a = svc.add_photo(F, None, photo(), {"eggs": item(6)})
    clock.advance(301)
    b = svc.add_photo(F, None, photo(), {"milk": item(1)})
    assert a.id != b.id
    old = store.get_snapshot(a.id)
    assert old.closed_by == "timeout" and old.full is False


def test_same_media_group_joins_even_after_window():
    svc, _, clock = make()
    a = svc.add_photo(F, "g1", photo(), {"eggs": item(1)})
    clock.advance(400)
    assert svc.add_photo(F, "g1", photo(), {"milk": item(1)}).id == a.id


def test_other_location_is_a_separate_session():
    svc, _, _ = make()
    a = svc.add_photo(F, None, photo(), {"eggs": item(1)})
    b = svc.add_photo(Location.FREEZER, None, photo(), {"ice_cream": item(1)})
    assert a.id != b.id


def test_seen_items_upserted_and_unseen_untouched_until_full_close():
    svc, store, clock = make()
    svc.add_photo(F, None, photo(), {"milk": item(2)})
    clock.advance(3600)
    svc.add_photo(F, None, photo(), {"eggs": item(3, uncertain=True)})
    inv = {e.key: e for e in store.get_inventory(F)}
    assert inv["milk"].count == 2 and inv["eggs"].count == 3 and inv["eggs"].uncertain

    closed, zeroed = svc.close(None)
    assert closed.full and closed.closed_by == "done"
    assert zeroed == ["milk"]
    inv = {e.key: e for e in store.get_inventory(F)}
    assert inv["milk"].count == 0 and inv["eggs"].count == 3


def test_full_close_does_not_touch_other_locations():
    svc, store, clock = make()
    svc.add_photo(Location.FREEZER, None, photo(), {"ice_cream": item(1)})
    clock.advance(3600)
    svc.add_photo(F, None, photo(), {"eggs": item(1)})
    svc.close(None)
    assert {e.key: e.count for e in store.get_inventory(Location.FREEZER)} == {"ice_cream": 1}


def test_close_without_open_session_returns_none():
    svc, _, clock = make()
    assert svc.close(None) == (None, [])
    svc.add_photo(F, None, photo(), {"eggs": item(1)})
    clock.advance(301)
    assert svc.close(None) == (None, [])


def test_merge_keeps_uncertain_from_higher_count():
    svc, _, _ = make()
    svc.add_photo(F, None, photo(), {"eggs": item(2, uncertain=True)})
    s = svc.add_photo(F, None, photo(), {"eggs": item(5)})
    assert s.items["eggs"].count == 5 and not s.items["eggs"].uncertain
