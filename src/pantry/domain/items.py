"""Item list and name matching in Hebrew and English (FR-009, R6)."""

import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path

import yaml

from pantry.domain.models import ItemType, Location

_FINALS = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})
_NIQQUD = re.compile(r"[֑-ׇ]")
_NON_WORD = re.compile(r"[^\w\s]")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _NIQQUD.sub("", text).translate(_FINALS).lower()
    text = _NON_WORD.sub(" ", text)
    return " ".join(text.split())


def load_item_types(path: Path) -> list[ItemType]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))["items"]
    return [
        ItemType(
            key=i["key"],
            name_he=i["name_he"],
            aliases=tuple(i.get("aliases", [])),
            prompt=i.get("prompt", ""),
            location_hint=Location(i["location_hint"]) if i.get("location_hint") else None,
        )
        for i in raw
    ]


class ItemCatalog:
    def __init__(self, items: Iterable[ItemType]):
        self._by_key: dict[str, ItemType] = {}
        self._by_name: dict[str, ItemType] = {}
        for item in items:
            self.add(item)

    def add(self, item: ItemType) -> None:
        self._by_key[item.key] = item
        for name in (item.key, item.name_he, *item.aliases):
            norm = normalise(name.replace("_", " "))
            owner = self._by_name.get(norm)
            if owner and owner.key != item.key:
                raise ValueError(f"name '{name}' used by {owner.key} and {item.key}")
            self._by_name[norm] = item

    def get(self, key: str) -> ItemType | None:
        return self._by_key.get(key)

    def keys(self) -> list[str]:
        return list(self._by_key)

    def resolve(self, name: str) -> ItemType | None:
        norm = normalise(name)
        found = self._by_name.get(norm)
        # Hebrew definite article or "and" prefix: הביצים, וחלב
        if not found and len(norm) > 2 and norm[0] in "הו":
            found = self._by_name.get(norm[1:])
        return found
