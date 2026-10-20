"""Owner request 2026-10-20: add new locations from the chat and use them everywhere."""

from tests.integration.conftest import box

DAY = 24 * 3600


def add_second_fridge(h) -> str:
    reply = h.text("מיקום חדש: מקרר שני")
    assert reply.startswith("נוסף מיקום: מקרר שני")
    return next(t.key for t in h.store.list_location_types() if t.name_he == "מקרר שני")


def test_new_location_works_for_photos_queries_and_corrections(h):
    key = add_second_fridge(h)
    reply = h.photo([box("beer")], caption="מקרר שני")
    assert reply.startswith("במקרר שני:")
    assert h.counts(key) == {"beer": 1}
    h.text("מקרר שני: חלב 2")
    assert h.counts(key) == {"beer": 1, "milk": 2}
    assert "חלב ×2" in h.text("מה יש במקרר שני")
    assert "במקרר שני:" in h.text("מה יש לי")


def test_list_locations(h):
    add_second_fridge(h)
    assert h.text("מיקומים") == "מיקומים: מקרר, מקפיא, מזווה, מקרר שני"


def test_duplicate_location_is_refused(h):
    assert h.text("מיקום חדש: מקפיא") == 'כבר יש מיקום בשם "מקפיא".'
    assert h.store.list_location_types() == []


def test_morning_names_the_new_location(h):
    key = add_second_fridge(h)
    h.photo([box("beer")], caption="מקרר שני")
    h.morning()
    h.clock.advance(DAY)
    h.text("מקרר שני: אין בירה")
    h.morning()
    assert "בירה (מקרר שני)" in h.last_text()
    assert h.counts(key) == {"beer": 0}
