"""Deterministic text grammar, no LLM (research R6): queries, corrections, captions and "done"."""

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
_ADD = re.compile(r"^(?:להוסיף|add)\s+(.+)$", re.IGNORECASE)
_REMOVE = re.compile(r"^(?:אין|no)\s+(.+)$", re.IGNORECASE)
_NAME_N = re.compile(r"^(\D.*?)\s+(\d+)$")
_N_NAME = re.compile(r"^(\d+)\s+(\D.*)$")


@dataclass(frozen=True)
class Query:
    location: Location | None


@dataclass(frozen=True)
class Has:
    name: str


@dataclass(frozen=True)
class SetCount:
    name: str
    count: int


@dataclass(frozen=True)
class Remove:
    name: str


@dataclass(frozen=True)
class Add:
    name: str
    count: int


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


def _name_and_count(text: str) -> tuple[str, int | None]:
    if m := _NAME_N.match(text):
        return m.group(1), int(m.group(2))
    if m := _N_NAME.match(text):
        return m.group(2), int(m.group(1))
    return text, None


Intent = Query | Has | SetCount | Remove | Add | Done | Unknown


_LOCATION_PREFIX = re.compile(r"^\s*([^:\s]+)\s*:\s*(.*)$")


def split_location(segment: str) -> tuple[Location | None, str]:
    """ "מקפיא: גלידה 2" -> (freezer, "גלידה 2"); a bare "מקפיא:" sets the location for following lines."""
    m = _LOCATION_PREFIX.match(segment)
    if m and (loc := _location_word(m.group(1))):
        return loc, m.group(2).strip()
    return None, segment


def split_lines(text: str) -> list[str]:
    """A message can carry several corrections, one per line or separated by commas."""
    return [part.strip() for line in text.splitlines() for part in line.split(",") if part.strip()]


def parse_text(text: str) -> Intent:
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
    raw = (text or "").strip().rstrip("?!. ")
    if m := _ADD.match(raw):
        name, count = _name_and_count(m.group(1))
        return Add(name, 1 if count is None else count)
    if m := _REMOVE.match(raw):
        return Remove(m.group(1))
    name, count = _name_and_count(raw)
    if count is not None:
        return SetCount(name, count)
    return Unknown()
