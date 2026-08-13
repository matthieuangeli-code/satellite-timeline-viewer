from datetime import date

import pytest

from satellite import bbox_from_point, parse_scenes


def feature(identifier, acquired, cloud, visual=True):
    return {
        "id": identifier,
        "properties": {"datetime": acquired, "eo:cloud_cover": cloud},
        "assets": {"visual": {"href": f"https://example.test/{identifier}.tif"}}
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

