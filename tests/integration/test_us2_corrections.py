"""User Story 2 - Correct the bot: acceptance scenarios plus buttons, English and reply targeting."""

from pantry.domain.models import Location
from tests.integration.conftest import box


def test_scenario_1_count_correction_updates_and_confirms(h):
    """Given the bot reported "ביצים ×6", When the owner replies "ביצים 4", Then the inventory shows 4 eggs
    and the bot confirms the change."""
    h.photo([box("eggs", i=i) for i in range(6)])
    snap_id = h.store.latest_snapshot().id
    assert h.text("ביצים 4") == "עודכן: ביצים ×4"
    assert h.counts()["eggs"] == 4
    [c] = h.store.corrections
    assert (c.key, c.kind, c.old_count, c.new_count, c.snapshot_id) == ("eggs", "count", 6, 4, snap_id)


def test_scenario_2_add_missed_item(h):
    """Given the bot missed hummus, When the owner replies "להוסיף חומוס", Then hummus ×1 is added and
    recorded as a missed detection for that photo."""
    h.photo([box("eggs")])
    assert h.text("להוסיף חומוס") == "עודכן: חומוס ×1"
    assert h.counts()["hummus"] == 1
    assert h.store.corrections[-1].kind == "missed"


def test_scenario_3_unknown_item_asks_before_adding(h):
    """Given a correction naming an item not in the known item list, When it is sent, Then the bot asks
    whether to add it as a new item type instead of guessing."""
    h.photo([box("eggs")])
    assert h.text("להוסיף קולרבי 2") == 'לא מכיר "קולרבי". להוסיף כסוג מוצר חדש?'
    assert h.button_data() == ["newitem:yes", "newitem:no"]
    assert "קולרבי" not in {i.name_he for i in h.store.list_item_types()}
    h.tap("newitem:yes")
    new = next(i for i in h.store.list_item_types() if i.name_he == "קולרבי")
    assert new.added_by == "owner"
    assert h.counts()[new.key] == 2
    assert h.last_text() == "עודכן: קולרבי ×2"
    assert h.store.corrections[-1].kind == "missed"


def test_unknown_item_declined_changes_nothing(h):
    h.photo([box("eggs")])
    h.text("להוסיף קולרבי")
    h.tap("newitem:no")
    assert "קולרבי" not in {i.name_he for i in h.store.list_item_types()}
    assert h.store.corrections == []


def test_new_item_question_expires_after_ten_minutes(h):
    h.photo([box("eggs")])
    h.text("להוסיף קולרבי")
    h.clock.advance(601)
    h.tap("newitem:yes")
    assert "קולרבי" not in {i.name_he for i in h.store.list_item_types()}


def test_english_remove_works_like_hebrew(h):
    """Edge case: "Hebrew and English item names in corrections ("milk" / "חלב") map to the same item
    type"."""
    h.photo([box("milk"), box("milk", i=1)])
    assert h.text("no milk") == "עודכן: חלב ×0"
    assert h.counts()["milk"] == 0
    assert h.store.corrections[-1].kind == "false"
    h.text("add milk 3")
    assert h.counts()["milk"] == 3


def test_confirm_button_clears_uncertain(h):
    h.verifier.answers = [RuntimeError("down")]
    h.photo([box("hummus", score=0.2)])
    snap_id = h.store.latest_snapshot().id
    h.tap(f"confirm:{snap_id}:hummus")
    assert not h.entry("hummus").uncertain and h.entry("hummus").count == 1
    assert h.store.corrections[-1].kind == "confirm"
    assert h.telegram.answered[-1][0].startswith("cb")


def test_remove_button_sets_zero_and_drops_its_row(h):
    h.verifier.answers = [RuntimeError("down"), RuntimeError("down")]
    h.photo([box("hummus", score=0.2), box("tahini", score=0.2, i=1)])
    reply_id = h.telegram.sent[-1].message_id
    snap_id = h.store.latest_snapshot().id
    h.tap(f"remove:{snap_id}:hummus", reply_id)
    assert h.entry("hummus").count == 0
    assert h.store.corrections[-1].kind == "false"
    chat_id, message_id, buttons = h.telegram.markups[-1]
    assert message_id == reply_id
    assert [d for row in buttons for _, d in row] == [f"confirm:{snap_id}:tahini", f"remove:{snap_id}:tahini"]


def test_reply_targets_that_snapshot_location(h):
    h.photo([box("eggs", i=i) for i in range(6)])
    fridge_reply = h.telegram.sent[-1].message_id
    h.clock.advance(600)
    h.photo([box("ice_cream")], caption="מקפיא")
    h.text("ביצים 2", reply_to=fridge_reply)
    assert h.counts("fridge")["eggs"] == 2
    assert "eggs" not in h.counts("freezer")


def test_without_reply_latest_snapshot_is_the_target(h):
    h.photo([box("eggs")])
    h.clock.advance(600)
    h.photo([box("ice_cream")], caption="מקפיא")
    h.text("להוסיף עוף")
    assert h.counts("freezer")["chicken"] == 1
    assert h.store.corrections[-1].snapshot_id == h.store.latest_snapshot(Location.FREEZER).id


def test_unrecognised_text_gets_help(h):
    assert h.text("בלה בלה").startswith("לא הבנתי")


def test_symbol_only_or_overlong_names_are_not_offered_as_new_items(h):
    """Security review: a name that normalises to nothing must never become an item type."""
    h.photo([box("eggs")])
    assert h.text("להוסיף !!!").startswith("לא הבנתי")
    assert h.text("להוסיף " + "א" * 41).startswith("לא הבנתי")
    assert h.store.pending == {}


def test_clashing_new_name_is_refused_and_bot_keeps_working(h):
    from pantry.domain.models import PendingQuestion

    h.photo([box("eggs")])
    # A pending name that slipped past resolve but clashes after normalisation
    h.store.set_pending(PendingQuestion(111, "new_item", "milk", None, 1, h.clock.now()))
    h.tap("newitem:yes")
    assert h.last_text() == "בסדר, לא הוספתי."
    assert sum(1 for i in h.store.list_item_types() if i.added_by == "owner") == 0
    assert "ביצים" in h.text("מה יש לי")


def test_bad_stored_item_is_skipped_not_fatal(h):
    from pantry.domain.models import ItemType

    h.store.upsert_item_type(ItemType("owner_bad", "חלב", added_by="owner"))
    h.photo([box("eggs")])
    assert "ביצים ×1" in h.text("מה יש לי")


def test_button_tap_still_applies_when_telegram_refresh_fails(h):
    h.verifier.answers = [RuntimeError("down")]
    h.photo([box("hummus", score=0.2)])
    snap_id = h.store.latest_snapshot().id

    def broken(*args, **kwargs):
        raise RuntimeError("telegram editMessageReplyMarkup 400: Bad Request")

    h.telegram.set_buttons = broken
    h.telegram.answer_callback = broken
    sent = len(h.telegram.sent)
    h.tap(f"remove:{snap_id}:hummus")
    assert h.entry("hummus").count == 0
    assert len(h.telegram.sent) == sent  # no "משהו השתבש" error message
