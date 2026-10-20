"""Configurable locations: defaults from config, owner-added ones, multi-word names."""

import pytest

from pantry.domain.locations import LocationCatalog, LocationType, default_location_types
from pantry.domain.models import Location


@pytest.fixture
def catalog():
    return LocationCatalog(
        [*default_location_types(), LocationType("loc_ab12", "מקרר שני", added_by="owner")]
    )


def test_defaults_keep_the_built_in_keys():
    keys = [t.key for t in default_location_types()]
    assert keys == ["fridge", "freezer", "pantry"]
    assert Location.FRIDGE == "fridge" and Location("loc_ab12").value == "loc_ab12"


@pytest.mark.parametrize(
    "word, key",
    [
        ("מקרר", "fridge"),
        ("במקפיא", "freezer"),
        ("pantry", "pantry"),
        ("מקרר שני", "loc_ab12"),
        ("במקרר שני", "loc_ab12"),
        ("מרפסת", None),
    ],
)
def test_match_word(catalog, word, key):
    found = catalog.match(word)
    assert (found.value if found else None) == key


def test_caption_prefers_the_longest_name(catalog):
    assert catalog.find_in("מקרר שני למעלה") == "loc_ab12"
    assert catalog.find_in("המקרר") is None or catalog.find_in("המקרר") == "fridge"
    assert catalog.find_in("מקרר") == "fridge"
    assert catalog.find_in("סתם") is None


def test_names_and_order(catalog):
    assert catalog.name("loc_ab12") == "מקרר שני" and catalog.name("unknown") == "unknown"
    assert catalog.keys() == ["fridge", "freezer", "pantry", "loc_ab12"]


def test_duplicate_or_empty_names_are_rejected(catalog):
    with pytest.raises(ValueError):
        catalog.add(LocationType("loc_x", "מקפיא", added_by="owner"))
    with pytest.raises(ValueError):
        catalog.add(LocationType("loc_y", "!!!", added_by="owner"))
