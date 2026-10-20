"""Query, location caption and done parsing (FR-006, contracts/bot-commands.md)."""

import pytest

from pantry.bot.commands import Done, Has, Query, Unknown, parse_location, parse_text
from pantry.domain.models import Location


@pytest.mark.parametrize(
    "text, intent",
    [
        ("מה יש לי", Query(None)),
        ("מה יש לי?", Query(None)),
        ("מה יש", Query(None)),
        ("מה יש לי במקרר?", Query(Location.FRIDGE)),
        ("מה יש במקפיא", Query(Location.FREEZER)),
        ("מה יש לי במזווה", Query(Location.PANTRY)),
        ("יש ביצים?", Has("ביצים")),
        ("יש ביצים", Has("ביצים")),
        ("יש גבינה צהובה?", Has("גבינה צהובה")),
        ("סיימתי", Done()),
        ("done", Done()),
        ("Done!", Done()),
        ("שלום", Unknown()),
        ("", Unknown()),
    ],
)
def test_parse_text(text, intent):
    assert parse_text(text) == intent


@pytest.mark.parametrize(
    "caption, location",
    [
        ("מקפיא", Location.FREEZER),
        ("freezer", Location.FREEZER),
        ("במזווה", Location.PANTRY),
        ("Fridge", Location.FRIDGE),
        ("סתם", None),
        (None, None),
    ],
)
def test_parse_location(caption, location):
    assert parse_location(caption) == location
