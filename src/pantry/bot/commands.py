"""Deterministic text grammar, no LLM (research R6): queries, corrections, captions, locations, "done"."""

import re
from dataclasses import dataclass

from pantry.domain.items import normalise
from pantry.domain.locations import LocationCatalog
from pantry.domain.models import Location

_DONE = {"סיימתי", "סיימנו", "זהו", "done"}
_LIST_LOCATIONS = {normalise("מיקומים"), "locations"}
_QUERY = re.compile(r"^מה יש( לי)?( (.+))?$")
_HAS = re.compile(r"^\s*יש\s+(.+?)[\s?!.]*$")
_ADD = re.compile(r"^(?:להוסיף|add)\s+(.+)$", re.IGNORECASE)
_REMOVE = re.compile(r"^(?:אין|no)\s+(.+)$", re.IGNORECASE)
_NEW_LOCATION = re.compile(r"^\s*(?:מיקום חדש|new location)\s*:?\s*(.+?)\s*$", re.IGNORECASE)
_NAME_N = re.compile(r"^(\D.*?)\s+(\d+)$")
_N_NAME = re.compile(r"^(\d+)\s+(\D.*)$")
_LOCATION_PREFIX = re.compile(r"^\s*([^:]+?)\s*:\s*(.*)$")


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
class NewLocation:
    name: str


@dataclass(frozen=True)
class ListLocations:
    pass


@dataclass(frozen=True)
class Unknown:
    pass


Intent = Query | Has | SetCount | Remove | Add | Done | NewLocation | ListLocations | Unknown


def _catalog(locations: LocationCatalog | None) -> LocationCatalog:
    return locations or LocationCatalog.merged([])


def parse_location(caption: str | None, locations: LocationCatalog | None = None) -> Location | None:
    return _catalog(locations).find_in(caption) if caption else None


def split_location(segment: str, locations: LocationCatalog | None = None) -> tuple[Location | None, str]:
    """ "מקפיא: גלידה 2" -> (freezer, "גלידה 2"); a bare "מקפיא:" sets the location for following lines."""
    m = _LOCATION_PREFIX.match(segment)
    if m and (loc := _catalog(locations).match(m.group(1))):
        return loc, m.group(2).strip()
    return None, segment


def split_lines(text: str) -> list[str]:
    """A message can carry several corrections, one per line or separated by commas."""
    return [part.strip() for line in text.splitlines() for part in line.split(",") if part.strip()]


def _name_and_count(text: str) -> tuple[str, int | None]:
    if m := _NAME_N.match(text):
        return m.group(1), int(m.group(2))
    if m := _N_NAME.match(text):
        return m.group(2), int(m.group(1))
    return text, None


def parse_text(text: str, locations: LocationCatalog | None = None) -> Intent:
    norm = normalise(text or "")
    if not norm:
        return Unknown()
    if norm in _DONE:
        return Done()
    if norm in _LIST_LOCATIONS:
        return ListLocations()
    if m := _NEW_LOCATION.match(text or ""):
        return NewLocation(m.group(1).strip())
    if m := _QUERY.match(norm):
        if m.group(3) is None:
            return Query(None)
        loc = _catalog(locations).match(m.group(3))
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
