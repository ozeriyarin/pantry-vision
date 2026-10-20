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
    def __init__(self, items: Iterable[ItemType], strict: bool = True):
        self._by_key: dict[str, ItemType] = {}
        self._by_name: dict[str, ItemType] = {}
        self.skipped: list[str] = []
        for item in items:
            try:
                self.add(item)
            except ValueError:
                if strict:
                    raise
                # One bad stored item must not take the whole bot down.
                self.skipped.append(item.key)

    def add(self, item: ItemType) -> None:
        names = [normalise(n.replace("_", " ")) for n in (item.key, item.name_he, *item.aliases)]
        for name, norm in zip((item.key, item.name_he, *item.aliases), names, strict=True):
            if not norm:
                raise ValueError(f"name '{name}' of {item.key} is empty after normalisation")
            owner = self._by_name.get(norm)
            if owner and owner.key != item.key:
                raise ValueError(f"name '{name}' used by {owner.key} and {item.key}")
        self._by_key[item.key] = item
        for norm in names:
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
