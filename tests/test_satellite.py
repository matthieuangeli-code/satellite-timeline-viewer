from datetime import date

import numpy as np

import pytest

from satellite import (
    MAX_AREA_WIDTH_KM,
    SENTINEL2_ARCHIVE_START,
    SatelliteError,
    _validated_rgb,
    bbox_from_point,
    parse_scenes,
    search_scenes,
)


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
        bbox_from_point(0, 0, MAX_AREA_WIDTH_KM + 1)


def test_bbox_supports_large_delta_window():
    west, south, east, north = bbox_from_point(30, 20, 300)
    assert west < 20 < east
    assert south < 30 < north
    assert (north - south) * 110.574 == pytest.approx(300, rel=0.01)


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


def test_parse_scenes_keeps_adjacent_tiles_for_a_cross_boundary_mosaic():
    left = feature("left", "2026-08-10T10:00:10Z", 1)
    left["bbox"] = [0, 0, 5, 5]
    right = feature("right", "2026-08-10T10:00:20Z", 2)
    right["bbox"] = [5, 0, 10, 5]

    scenes = parse_scenes([left, right], target_bbox=(4, 1, 6, 4))

    assert len(scenes) == 1
    assert scenes[0].visual_hrefs == (
        "https://example.test/left.tif",
        "https://example.test/right.tif",
    )
    assert scenes[0].preview_hrefs == (
        "https://example.test/left-preview.tif",
        "https://example.test/right-preview.tif",
    )


def test_black_frame_is_rejected():
    with pytest.raises(SatelliteError, match="Black"):
        _validated_rgb(np.zeros((3, 40, 40), dtype=np.uint8))


def test_frame_with_black_border_is_rejected():
    data = np.full((3, 40, 40), 80, dtype=np.uint8)
    data[:, :, :2] = 0
    with pytest.raises(SatelliteError, match="Black"):
        _validated_rgb(data)


def test_complete_non_black_frame_is_accepted():
    ramp = np.tile(np.arange(1, 41, dtype=np.uint8), (40, 1))
    data = np.stack([ramp + 10, ramp + 20, ramp + 30])
    rgb = _validated_rgb(data)
    assert rgb.shape == (40, 40, 3)
    assert rgb.dtype == np.uint8


def test_archive_starts_with_first_catalogued_sentinel_2_image():
    assert SENTINEL2_ARCHIVE_START == date(2015, 6, 27)


def test_search_follows_all_catalogue_pages(monkeypatch):
    pages = [
        {
            "features": [feature("first", "2020-01-01T10:00:00Z", 2)],
            "links": [
                {
                    "rel": "next",
                    "href": "https://example.test/search",
                    "method": "POST",
                    "body": {"token": "page-2"},
                }
            ],
        },
        {
            "features": [feature("second", "2020-01-06T10:00:00Z", 3)],
            "links": [],
        },
    ]
    calls = []

    class Response:
        def __init__(self, page):
            self.page = page

        def raise_for_status(self):
            return None

        def json(self):
            return self.page

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return Response(pages.pop(0))

    monkeypatch.setattr("satellite.requests.post", fake_post)
    scenes = search_scenes(
        (1.0, 2.0, 3.0, 4.0), date(2019, 1, 1), date(2021, 1, 1), 20
    )

    assert [scene.id for scene in scenes] == ["first", "second"]
    assert len(calls) == 2
    assert calls[1][1] == {"token": "page-2"}


def test_search_retries_transient_catalogue_500(monkeypatch):
    calls = []

    class Response:
        def __init__(self, status_code, page=None):
            self.status_code = status_code
            self.page = page or {"features": [], "links": []}

        def raise_for_status(self):
            if self.status_code >= 400:
                error = __import__("requests").HTTPError("temporary server error")
                error.response = self
                raise error

        def json(self):
            return self.page

    responses = [Response(500), Response(502), Response(200)]

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return responses.pop(0)

    monkeypatch.setattr("satellite.requests.post", fake_post)
    monkeypatch.setattr("satellite.time.sleep", lambda _seconds: None)

    scenes = search_scenes(
        (1.0, 2.0, 3.0, 4.0), date(2026, 1, 1), date(2026, 2, 1), 20
    )

    assert scenes == []
    assert len(calls) == 3
    assert calls[0][1]["limit"] == 100
