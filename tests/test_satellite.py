from datetime import date

import pytest

from satellite import bbox_from_point, parse_scenes


def feature(identifier, acquired, cloud, visual=True):
    return {
        "id": identifier,
        "properties": {"datetime": acquired, "eo:cloud_cover": cloud},
        "bbox": [1.0, 2.0, 3.0, 4.0],
        "assets": {
            "visual": {"href": f"https://example.test/{identifier}.tif"},
            "preview": {"href": f"https://example.test/{identifier}-preview.tif"},
        }
        if visual
        else {},
    }


def test_bbox_has_requested_height_near_equator():
    west, south, east, north = bbox_from_point(0, 0, 10)
    assert (north - south) * 110.574 == pytest.approx(10, rel=0.01)
    assert west < 0 < east


def test_bbox_validates_inputs():
    with pytest.raises(ValueError):
        bbox_from_point(91, 0, 5)
    with pytest.raises(ValueError):
        bbox_from_point(0, 0, 100)


def test_bbox_supports_large_delta_window():
    west, south, east, north = bbox_from_point(30, 20, 46)
    assert west < 20 < east
    assert south < 30 < north


def test_parse_scenes_sorts_and_keeps_clearer_overlap():
    features = [
        feature("new-cloudy", "2026-08-10T10:00:30Z", 70),
        feature("old", "2026-08-01T10:00:00Z", 5),
        feature("new-clear", "2026-08-10T10:00:10Z", 12),
        feature("no-visual", "2026-08-12T10:00:00Z", 0, visual=False),
    ]
    scenes = parse_scenes(features)
    assert [scene.id for scene in scenes] == ["old", "new-clear"]
    assert scenes[-1].cloud_cover == 12
    assert scenes[-1].preview_href.endswith("new-clear-preview.tif")


def test_parse_scenes_prefers_tile_covering_selected_area():
    left = feature("left", "2026-08-10T10:00:10Z", 1)
    left["bbox"] = [0, 0, 5, 5]
    right = feature("right", "2026-08-10T10:00:20Z", 90)
    right["bbox"] = [5, 0, 10, 5]
    scenes = parse_scenes([left, right], target_bbox=(6, 1, 8, 4))
    assert [scene.id for scene in scenes] == ["right"]
