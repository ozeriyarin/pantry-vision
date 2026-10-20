"""Locations as data: built-in ones from config, owner-added ones from the store."""

from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

import yaml

from pantry.config import ROOT
from pantry.domain.items import normalise
from pantry.domain.models import Location


@dataclass(frozen=True)
class LocationType:
    key: str
    name_he: str
    aliases: tuple[str, ...] = ()
    added_by: Literal["seed", "owner"] = "seed"


@cache
def default_location_types(path: Path = ROOT / "config/locations.yaml") -> tuple[LocationType, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["locations"]
    return tuple(LocationType(r["key"], r["name_he"], tuple(r.get("aliases", []))) for r in raw)


class LocationCatalog:
    def __init__(self, types: Iterable[LocationType]):
        self._types: dict[str, LocationType] = {}
        self._by_name: dict[str, str] = {}
        for t in types:
            try:
                self.add(t)
            except ValueError:
                continue  # a clashing stored location must not break the bot

    @classmethod
    def merged(cls, stored: Iterable[LocationType]) -> "LocationCatalog":
        return cls([*default_location_types(), *stored])

    def add(self, t: LocationType) -> None:
        names = [normalise(n) for n in (t.key.replace("_", " "), t.name_he, *t.aliases)]
        for norm in names:
            if not norm:
                raise ValueError(f"location {t.key} has an empty name")
            if self._by_name.get(norm, t.key) != t.key:
                raise ValueError(f"location name '{norm}' already used")
        self._types[t.key] = t
        for norm in names:
            self._by_name[norm] = t.key

    def has_name(self, name: str) -> bool:
        return normalise(name) in self._by_name

    def keys(self) -> list[Location]:
        return [Location(k) for k in self._types]

    def name(self, key: str) -> str:
        t = self._types.get(str(key))
        return t.name_he if t else str(key)

    def match(self, text: str) -> Location | None:
        """A whole phrase naming a location, with an optional "ב" prefix: "במקרר שני"."""
        norm = normalise(text)
        for candidate in (norm, norm[1:] if norm.startswith("ב") else None):
            if candidate and candidate in self._by_name:
                return Location(self._by_name[candidate])
        return None

    def find_in(self, text: str) -> Location | None:
        """The longest location name appearing as whole words in a caption."""
        words = normalise(text).split()
        best, best_len = None, 0
        for i in range(len(words)):
            for j in range(len(words), i, -1):
                if j - i > best_len and (loc := self.match(" ".join(words[i:j]))):
                    best, best_len = loc, j - i
        return best
