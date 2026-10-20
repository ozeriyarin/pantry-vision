"""Pure parts of the cloud adapters; the network calls are covered at deploy (quickstart step 5)."""

from datetime import UTC, datetime

from pantry.adapters.firestore_store import inventory_from, item_type_from, plain, snapshot_from
from pantry.adapters.gcs_blob import photo_path
from pantry.domain.models import (
    Detection,
    FallbackResult,
    InventoryEntry,
    ItemType,
    Location,
    RunRecord,
    Snapshot,
    SnapshotItem,
    SnapshotPhoto,
)

NOW = datetime(2026, 10, 20, 9, 30, tzinfo=UTC)


def test_snapshot_round_trip():
    snap = Snapshot(
        id="s1",
        location=Location.FREEZER,
        opened_at=NOW,
        last_photo_at=NOW,
        media_group_id="g1",
        photos=[
            SnapshotPhoto(
                "photos/2026/10/20/a.jpg",
                "file1",
                [Detection("eggs", (1.0, 2.0, 3.0, 4.0), 0.3, FallbackResult("eggs", 6, 0.0001))],
            )
        ],
        items={"eggs": SnapshotItem(6, 0.3, False, "fallback")},
        closed_by="done",
        full=True,
        reply_message_ids=[5],
    )
    doc = plain(snap)
    assert doc["location"] == "freezer" and doc["photos"][0]["detections"][0]["box"] == [1.0, 2.0, 3.0, 4.0]
    assert snapshot_from(doc) == snap


def test_inventory_and_item_type_round_trip():
    entry = InventoryEntry(Location.PANTRY, "rice", 2, False, NOW, "s1")
    assert inventory_from(plain(entry)) == entry
    item = ItemType("kohlrabi", "קולרבי", ("kohlrabi",), "", Location.FRIDGE, "owner")
    assert item_type_from(plain(item)) == item


def test_run_record_has_no_image_fields():
    """FR-013: a record per photo "and no image data"."""
    names = set(RunRecord.__dataclass_fields__)
    assert not names & {"image", "photo", "bytes", "data", "crop", "caption"}


def test_photo_path_is_dated_under_photos_prefix():
    path = photo_path(NOW)
    assert path.startswith("photos/2026/10/20/") and path.endswith(".jpg")
