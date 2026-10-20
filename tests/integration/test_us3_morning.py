"""User Story 3 - Morning heads-up: acceptance scenarios plus first run and once-a-day."""

from tests.conftest import OWNER
from tests.integration.conftest import box

DAY = 24 * 3600


def test_scenario_1_item_gone_since_previous_morning_is_listed(h):
    """Given milk was in the inventory at the previous morning message and the latest snapshot shows none,
    When the morning message is sent, Then it lists milk as run out."""
    h.photo([box("milk"), box("eggs")])
    h.morning()
    h.clock.advance(DAY)
    h.photo([box("eggs")])
    h.text("סיימתי")
    response = h.morning()
    assert response.json() == {"sent": 1, "run_out": 1}
    msg = h.telegram.sent[-1]
    assert msg.chat_id == OWNER
    assert msg.text == "בוקר טוב. נגמרו מאתמול:\nחלב (מקרר)"


def test_scenario_2_nothing_ran_out_sends_all_good(h):
    """Given nothing ran out since the previous morning, When the morning time comes, Then the bot sends a
    one-line "all good" message rather than nothing, so the owner knows it ran."""
    h.photo([box("milk")])
    h.morning()
    h.clock.advance(DAY)
    assert h.morning().json() == {"sent": 1, "run_out": 0}
    assert h.last_text() == "בוקר טוב, הכול בסדר."


def test_scenario_3_partial_session_does_not_report_run_out(h):
    """Given a partial session that did not show milk, When the morning message is sent, Then milk is not
    listed as run out."""
    h.photo([box("milk"), box("eggs")])
    h.morning()
    h.clock.advance(DAY)
    h.photo([box("eggs")])
    h.clock.advance(600)
    h.morning()
    assert h.last_text() == "בוקר טוב, הכול בסדר."


def test_first_run_without_baseline_sends_all_good_and_writes_one(h):
    h.photo([box("milk")])
    assert h.morning().json() == {"sent": 1, "run_out": 0}
    assert h.last_text() == "בוקר טוב, הכול בסדר."
    assert h.store.baseline.items == {"fridge__milk": 1}


def test_second_call_same_local_date_sends_nothing(h):
    h.morning()
    sent = len(h.telegram.sent)
    assert h.morning().json() == {"sent": 0, "run_out": 0}
    assert len(h.telegram.sent) == sent


def test_correction_to_zero_counts_as_run_out(h):
    h.photo([box("milk")])
    h.morning()
    h.clock.advance(DAY)
    h.text("אין חלב")
    h.morning()
    assert "חלב (מקרר)" in h.last_text()
