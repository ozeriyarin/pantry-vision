"""User Story 1 edge cases and scenarios 5-6 (photo sessions, research R5)."""

from pantry.domain.models import Budget
from tests.images import jpeg
from tests.integration.conftest import box


def test_dark_photo_asks_for_retake_and_leaves_inventory(h):
    h.photo([box("milk")])
    reply = h.photo([box("eggs")], image=jpeg(dark=True))
    assert reply == "התמונה לא ברורה, אפשר לצלם שוב?"
    assert h.counts() == {"milk": 1}


def test_blurry_photo_asks_for_retake(h):
    assert h.photo([box("eggs")], image=jpeg(flat=True)) == "התמונה לא ברורה, אפשר לצלם שוב?"


def test_scenario_5_partial_photo_keeps_unseen_items(h):
    """Given milk in the fridge inventory, When the owner sends a door photo without milk and does not send
    "סיימתי", Then milk keeps its count."""
    h.photo([box("milk"), box("milk", i=1)])
    h.clock.advance(3600)
    h.photo([box("eggs")])
    assert h.counts() == {"milk": 2, "eggs": 1}


def test_scenario_6_done_zeroes_unseen_items_and_lists_them(h):
    """Given an open fridge session, When the owner sends "סיימתי", Then fridge items not seen in the session
    are set to 0 and the bot lists them."""
    h.photo([box("milk")])
    h.clock.advance(3600)
    h.photo([box("eggs")])
    reply = h.text("סיימתי")
    assert "חלב" in reply
    assert h.counts() == {"milk": 0, "eggs": 1}


def test_done_without_open_session(h):
    assert h.text("סיימתי") == "אין צילום פתוח לסגור."


def test_overlapping_photos_merge_by_highest_count(h):
    h.photo([box("eggs", i=i) for i in range(6)] + [box("beer")])
    h.clock.advance(60)
    reply = h.photo([box("eggs", i=i) for i in range(4)] + [box("beer", i=1), box("beer", i=2)])
    assert "ביצים ×6" in reply and "בירה ×2" in reply
    assert h.counts() == {"eggs": 6, "beer": 2}


def test_photo_after_window_opens_new_session(h):
    h.photo([box("eggs", i=i) for i in range(6)])
    h.clock.advance(301)
    h.photo([box("eggs", i=i) for i in range(3)])
    assert h.counts() == {"eggs": 3}
    assert len(h.store.snapshots) == 2


def test_album_photos_share_session_and_caption(h):
    h.photo([box("ice_cream")], caption="מקפיא", media_group_id="g1")
    h.photo([box("chicken")], media_group_id="g1")
    assert h.counts("freezer") == {"ice_cream": 1, "chicken": 1}
    assert len(h.store.snapshots) == 1


def test_budget_exhausted_reports_items_not_checked(h):
    """Edge case: second step budget exhausted: "the bot replies with what the first step found and says
    some items may be missing; it never fails silently"."""
    month = h.clock.now().strftime("%Y-%m")
    h.store.budgets[month] = Budget(month, 5.0, 10, 1.0)
    reply = h.photo([box("eggs"), box("hummus", score=0.2, i=1)])
    assert "1 פריטים לא נבדקו שוב." in reply and "חומוס ×1 ?" in reply
    assert h.verifier.calls == 0


def test_run_record_written_without_image_data(h):
    h.photo([box("eggs", i=i) for i in range(2)])
    run = h.store.runs[-1]
    assert run.counts == {"eggs": 2} and run.detector_model == "fake-detector"
    assert run.latency_ms >= 0 and run.fallback_calls == 0
