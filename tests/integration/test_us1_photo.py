"""User Story 1 - Photo to inventory: acceptance scenarios 1-3 plus caption routing."""

from tests.integration.conftest import box


def test_scenario_1_photo_lists_items_and_query_returns_them(h):
    """Given an empty fridge inventory, When the owner sends a fridge photo containing 6 eggs and 2 milk
    cartons, Then the bot replies within 15 seconds listing "ביצים ×6" and "חלב ×2", and "מה יש לי במקרר?"
    returns the same items."""
    reply = h.photo([box("eggs", i=i) for i in range(6)] + [box("milk", i=i) for i in range(2)])
    assert "ביצים ×6" in reply and "חלב ×2" in reply
    answer = h.text("מה יש לי במקרר?")
    assert "ביצים ×6" in answer and "חלב ×2" in answer
    assert h.counts() == {"eggs": 6, "milk": 2}


def test_scenario_2_low_certainty_item_is_marked_uncertain(h):
    """Given a photo where one item is recognised with low certainty, When the reply is sent, Then that item
    is marked as uncertain (for example "?") rather than presented as fact."""
    h.verifier.answers = [RuntimeError("fallback unavailable")]
    reply = h.photo([box("eggs"), box("hummus", score=0.2, i=1)])
    assert "חומוס ×1 ?" in reply and "ביצים ×1 ?" not in reply
    entry = next(e for e in h.store.get_inventory() if e.key == "hummus")
    assert entry.uncertain
    buttons = h.telegram.sent[-1].buttons
    assert any(data.startswith("confirm:") and data.endswith(":hummus") for row in buttons for _, data in row)


def test_scenario_3_photo_without_food_leaves_inventory_unchanged(h):
    """Given a photo with no recognisable food items, When it is sent, Then the bot says it found nothing and
    leaves the inventory unchanged."""
    h.photo([box("milk")])
    before = h.counts()
    reply = h.photo([])
    assert reply == "לא מצאתי מוצרים בתמונה."
    assert h.counts() == before


def test_caption_freezer_routes_to_freezer_and_no_caption_means_fridge(h):
    h.photo([box("ice_cream")], caption="מקפיא")
    h.photo([box("milk")])
    assert h.counts("freezer") == {"ice_cream": 1}
    assert h.counts("fridge") == {"milk": 1}


def test_fallback_confirmed_item_is_certain(h):
    """Analyze M1: an item the second step confirms is no longer uncertain."""
    from pantry.domain.models import FallbackResult

    h.verifier.answers = [FallbackResult("hummus", 1, 0.0001)]
    reply = h.photo([box("hummus", score=0.2)])
    assert "חומוס ×1" in reply and "חומוס ×1 ?" not in reply


def test_has_item_query(h):
    h.photo([box("eggs", i=i) for i in range(4)])
    assert h.text("יש ביצים?") == "כן, ביצים ×4 במקרר"
    assert h.text("יש חלב?") == "אין חלב"
