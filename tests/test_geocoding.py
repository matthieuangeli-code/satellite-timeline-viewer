import pytest
import requests

from geocoding import GeocodingError, NOMINATIM_SEARCH_URL, search_places


class Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("geocoding failed")

    def json(self):
        return self.payload


def test_search_places_returns_valid_worldwide_matches(monkeypatch):
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        return Response(
            [
                {
                    "display_name": "Kathmandu, Nepal",
                    "lat": "27.708317",
                    "lon": "85.3205817",
                    "category": "place",
                    "type": "city",
                }
            ]
        )

    monkeypatch.setattr("geocoding.requests.get", fake_get)

    results = search_places("  Kathmandu   Nepal  ")

    assert results == [
        {
            "label": "Kathmandu, Nepal",
            "latitude": 27.708317,
            "longitude": 85.3205817,
            "category": "place",
            "type": "city",
        }
    ]
    assert calls[0][0] == NOMINATIM_SEARCH_URL
    assert calls[0][1]["q"] == "Kathmandu Nepal"
    assert calls[0][1]["limit"] == 5
    assert calls[0][2]["User-Agent"].startswith("SatelliteTimeline/")
    assert calls[0][3] == 20


def test_search_places_skips_invalid_results(monkeypatch):
    monkeypatch.setattr(
        "geocoding.requests.get",
        lambda *args, **kwargs: Response(
            [
                {"display_name": "Missing coordinates"},
                {"display_name": "Outside Earth", "lat": "95", "lon": "0"},
            ]
        ),
    )

    assert search_places("example") == []


def test_search_places_validates_query_before_request():
    with pytest.raises(GeocodingError, match="two characters"):
        search_places(" ")


def test_search_places_wraps_network_errors(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("geocoding.requests.get", fail)

    with pytest.raises(GeocodingError, match="temporarily unavailable"):
        search_places("Nepal")
