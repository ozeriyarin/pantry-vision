from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LOCATIONS = {"fridge", "freezer", "pantry", None}


def _items():
    return yaml.safe_load((ROOT / "config/items.yaml").read_text(encoding="utf-8"))["items"]


def test_item_keys_are_unique_lowercase_slugs():
    """data-model ItemType.key: "lowercase ascii slug, unique"."""
    keys = [i["key"] for i in _items()]
    assert len(keys) == len(set(keys))
    assert all(k.isascii() and k == k.lower() and k.replace("_", "").isalnum() for k in keys)


def test_aliases_are_unique_across_all_types():
    """data-model ItemType.aliases: "unique across all types"."""
    seen = {}
    for item in _items():
        for name in [item["name_he"], *item["aliases"]]:
            assert name not in seen, f"{name} in {item['key']} and {seen[name]}"
            seen[name] = item["key"]


def test_items_have_required_fields():
    for item in _items():
        assert item["name_he"] and item["prompt"]
        assert item["location_hint"] in LOCATIONS


def test_about_thirty_item_types():
    """FR-009: "about 30 Hebrew item types with English aliases"."""
    assert 25 <= len(_items()) <= 45


def test_settings_have_required_keys():
    s = yaml.safe_load((ROOT / "config/settings.yaml").read_text(encoding="utf-8"))
    assert 0 < s["min_score"] < s["uncertain_score"] < 1
    assert s["session_window_s"] == 300
    assert s["fallback"]["model"] == "claude-haiku-5-5"
    assert s["fallback"]["cap_usd"] <= 2
