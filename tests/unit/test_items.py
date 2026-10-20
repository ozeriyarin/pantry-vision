import pytest

from pantry.config import ROOT
from pantry.domain.items import ItemCatalog, load_item_types, normalise
from pantry.domain.models import ItemType


@pytest.fixture(scope="module")
def catalog():
    return ItemCatalog(load_item_types(ROOT / "config/items.yaml"))


def test_hebrew_and_english_names_map_to_same_type(catalog):
    """Edge case: "Hebrew and English item names in corrections ("milk" / "חלב") map to the same
    item type"."""
    assert catalog.resolve("milk").key == catalog.resolve("חלב").key == "milk"


def test_normalise_folds_finals_niqqud_punctuation_case():
    assert normalise("ביצים") == normalise("ביצימ")
    assert normalise("חָלָב") == "חלב"
    assert normalise("קוטג'") == "קוטג"
    assert normalise("  Cottage   Cheese ") == "cottage cheese"


def test_resolves_with_definite_article_and_vav_prefix(catalog):
    assert catalog.resolve("הביצים").key == "eggs"
    assert catalog.resolve("וחלב").key == "milk"


def test_unknown_name_returns_none(catalog):
    assert catalog.resolve("קולרבי") is None


def test_seed_list_has_no_cross_type_name_collisions(catalog):
    assert len(catalog.keys()) >= 25


def test_adding_owner_type_with_taken_name_is_rejected(catalog):
    with pytest.raises(ValueError):
        ItemCatalog([*map(catalog.get, catalog.keys()), ItemType(key="kohlrabi", name_he="חלב")])


def test_empty_after_normalisation_is_rejected():
    with pytest.raises(ValueError):
        ItemCatalog([ItemType(key="x1", name_he="!!!")])


def test_non_strict_catalog_skips_clashing_items(catalog):
    items = [*map(catalog.get, catalog.keys()), ItemType(key="owner_dup", name_he="חלב")]
    tolerant = ItemCatalog(items, strict=False)
    assert tolerant.skipped == ["owner_dup"] and tolerant.resolve("חלב").key == "milk"


def test_seed_writes_only_new_or_changed_and_keeps_owner_types():
    from pantry.domain.items import seed_item_types
    from tests.fakes import InMemoryStore

    store = InMemoryStore()
    owner = ItemType("owner_ab12", "קולרבי", added_by="owner")
    store.upsert_item_type(owner)
    seed = load_item_types(ROOT / "config/items.yaml")
    assert seed_item_types(store, seed) == len(seed)
    assert seed_item_types(store, seed) == 0
    assert store.item_types["owner_ab12"] == owner


def test_root_can_be_overridden_for_containers(monkeypatch, tmp_path):
    import importlib

    import pantry.config as config

    monkeypatch.setenv("PANTRY_ROOT", str(tmp_path))
    assert importlib.reload(config).ROOT == tmp_path
    monkeypatch.delenv("PANTRY_ROOT")
    importlib.reload(config)


@pytest.mark.parametrize(
    "name, key",
    [
        ("בירהה", "beer"),
        ("עגבנייות", "tomato"),
        ("ביצימ", "eggs"),
        ("חלב נטול לקטוז", None),
        ("קולרבי", None),
    ],
)
def test_suggest_close_names_only(catalog, name, key):
    found = catalog.suggest(name)
    assert (found.key if found else None) == key


@pytest.mark.parametrize("plural, key", [("בירות", "beer"), ("ריבות", "jam"), ("גלידות", "ice_cream")])
def test_common_plurals_resolve(catalog, plural, key):
    assert catalog.resolve(plural).key == key
