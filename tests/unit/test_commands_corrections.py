"""Every row of the corrections table in contracts/bot-commands.md."""

import pytest

from pantry.bot.commands import Add, Has, Remove, SetCount, Unknown, parse_text


@pytest.mark.parametrize(
    "text, intent",
    [
        ("ביצים 4", SetCount("ביצים", 4)),
        ("4 ביצים", SetCount("ביצים", 4)),
        ("גבינה צהובה 2", SetCount("גבינה צהובה", 2)),
        ("eggs 0", SetCount("eggs", 0)),
        ("אין חלב", Remove("חלב")),
        ("אין חלב!", Remove("חלב")),
        ("no milk", Remove("milk")),
        ("להוסיף חומוס", Add("חומוס", 1)),
        ("להוסיף חומוס 3", Add("חומוס", 3)),
        ("להוסיף 3 חומוס", Add("חומוס", 3)),
        ("add hummus", Add("hummus", 1)),
        ("Add hummus 2", Add("hummus", 2)),
        ("יש ביצים?", Has("ביצים")),
        ("ביצים", Unknown()),
        ("4", Unknown()),
    ],
)
def test_parse_corrections(text, intent):
    assert parse_text(text) == intent


@pytest.mark.parametrize(
    "text, location, rest",
    [
        ("מקפיא: גלידה 2", "freezer", "גלידה 2"),
        ("במזווה: אורז 3", "pantry", "אורז 3"),
        ("fridge: milk 1", "fridge", "milk 1"),
        ("מקרר:", "fridge", ""),
        ("גלידה 2", None, "גלידה 2"),
        ("שעה: 5", None, "שעה: 5"),
    ],
)
def test_split_location(text, location, rest):
    from pantry.bot.commands import split_location

    loc, remainder = split_location(text)
    assert (loc.value if loc else None, remainder) == (location, rest)
