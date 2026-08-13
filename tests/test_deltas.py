from collections import Counter

from deltas import DELTAS, DELTA_CATALOG_VERSION, DELTA_TYPES


def test_catalogue_contains_thirty_deltas():
    assert len(DELTAS) == 30


def test_catalogue_has_ten_deltas_per_type():
    counts = Counter(delta["type"] for delta in DELTAS.values())
    assert counts == Counter({delta_type: 10 for delta_type in DELTA_TYPES})


def test_delta_coordinates_and_windows_are_valid():
    for delta in DELTAS.values():
        assert -90 <= delta["latitude"] <= 90
        assert -180 <= delta["longitude"] <= 180
        assert 0.5 <= delta["width_km"] <= 80


def test_orinoco_preset_avoids_the_known_sentinel_tile_boundary():
    orinoco = DELTAS["Orinoco · Venezuela"]
    assert DELTA_CATALOG_VERSION >= 2
    assert orinoco["longitude"] == -61.45
    assert orinoco["width_km"] == 42
