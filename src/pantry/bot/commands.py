"""Deterministic text grammar, no LLM (research R6). Queries, captions and "done" in this story."""

import re
from dataclasses import dataclass

from pantry.domain.items import normalise
from pantry.domain.models import Location

_LOCATIONS = {
    "מקרר": Location.FRIDGE,
    "fridge": Location.FRIDGE,
    "מקפיא": Location.FREEZER,
    "freezer": Location.FREEZER,
    "מזווה": Location.PANTRY,
    "pantry": Location.PANTRY,
}
_DONE = {"סיימתי", "סיימנו", "זהו", "done"}
_QUERY = re.compile(r"^מה יש( לי)?( (\S+))?$")
_HAS = re.compile(r"^\s*יש\s+(.+?)[\s?!.]*$")


@dataclass(frozen=True)
class Query:
    location: Location | None


@dataclass(frozen=True)
class Has:
    name: str


@dataclass(frozen=True)
class Done:
    pass


@dataclass(frozen=True)
class Unknown:
    pass


def _location_word(word: str) -> Location | None:
    word = normalise(word)
    if word in _LOCATIONS:
        return _LOCATIONS[word]
    if word.startswith("ב") and word[1:] in _LOCATIONS:
        return _LOCATIONS[word[1:]]
    return None


def parse_location(caption: str | None) -> Location | None:
    if not caption:
        return None
    for word in normalise(caption).split():
        if loc := _location_word(word):
            return loc
    return None


def parse_text(text: str) -> Query | Has | Done | Unknown:
    norm = normalise(text or "")
    if not norm:
        return Unknown()
    if norm in _DONE:
        return Done()
    if m := _QUERY.match(norm):
        if m.group(3) is None:
            return Query(None)
        loc = _location_word(m.group(3))
        return Query(loc) if loc else Unknown()
    if norm.startswith("יש ") and (m := _HAS.match(text)):
        return Has(m.group(1))
    return Unknown()
