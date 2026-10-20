"""Domain types per specs/001-pantry-photo-inventory/data-model.md. No image bytes anywhere."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


class Location(str):
    """A location key: a built-in one below or an owner-added one (config/locations.yaml, Firestore)."""

    FRIDGE: "Location"
    FREEZER: "Location"
    PANTRY: "Location"

    @property
    def value(self) -> str:
        return str(self)


Location.FRIDGE = Location("fridge")
Location.FREEZER = Location("freezer")
Location.PANTRY = Location("pantry")


@dataclass(frozen=True)
class ItemType:
    key: str
    name_he: str
    aliases: tuple[str, ...] = ()
    prompt: str = ""
    location_hint: Location | None = None
    added_by: Literal["seed", "owner"] = "seed"


@dataclass(frozen=True)
class FallbackResult:
    item: str  # known item key or "none"
    count: int
    cost_usd: float


@dataclass(frozen=True)
class Detection:
    key: str
    box: tuple[float, float, float, float]
    score: float
    fallback: FallbackResult | None = None


@dataclass
class SnapshotItem:
    count: int
    score: float
    uncertain: bool
    source: Literal["detector", "fallback"]


@dataclass
class SnapshotPhoto:
    blob_path: str
    telegram_file_id: str
    detections: list[Detection] = field(default_factory=list)


@dataclass
class Snapshot:
    id: str
    location: Location
    opened_at: datetime
    last_photo_at: datetime
    media_group_id: str | None = None
    photos: list[SnapshotPhoto] = field(default_factory=list)
    items: dict[str, SnapshotItem] = field(default_factory=dict)
    closed_by: Literal["done", "timeout"] | None = None
    full: bool = False
    reply_message_ids: list[int] = field(default_factory=list)


@dataclass
class InventoryEntry:
    location: Location
    key: str
    count: int  # >= 0; 0 means known run out
    uncertain: bool
    last_seen_at: datetime
    snapshot_id: str

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError("count must be >= 0")


@dataclass(frozen=True)
class Correction:
    id: str
    snapshot_id: str
    key: str
    kind: Literal["count", "missed", "false", "confirm"]
    old_count: int
    new_count: int
    created_at: datetime
    text: str


@dataclass(frozen=True)
class RunRecord:
    id: str
    snapshot_id: str
    location: Location
    detector_model: str
    counts: dict[str, int]
    scores: dict[str, list[float]]
    uncertain_count: int
    fallback_calls: int
    fallback_skipped: int
    fallback_cost_usd: float
    latency_ms: int
    cold_start: bool
    created_at: datetime


@dataclass(frozen=True)
class Budget:
    month: str  # yyyy-mm
    spent_usd: float
    calls: int
    cap_usd: float


@dataclass(frozen=True)
class Baseline:
    taken_at: datetime
    items: dict[str, int]  # "location__key" -> count
    last_sent_date: str | None = None  # yyyy-mm-dd in the morning time zone


@dataclass(frozen=True)
class PendingQuestion:
    chat_id: int
    kind: Literal["new_item"]
    snapshot_id: str | None
    created_at: datetime
    # (name, count, "set" or "add", suggested existing key or "") per unknown name
    entries: tuple = ()


def inventory_id(location: Location, key: str) -> str:
    return f"{location.value}__{key}"
