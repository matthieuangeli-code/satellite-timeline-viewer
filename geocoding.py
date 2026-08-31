"""Text search for worldwide places using the public Nominatim service."""

from __future__ import annotations

from typing import Any

import requests


NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SatelliteTimeline/1.0 (personal Streamlit imagery explorer)"


class GeocodingError(RuntimeError):
    """Raised when a place search cannot be completed."""


def search_places(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Return a compact list of worldwide matches for a free-text query."""
    normalized_query = " ".join(query.split())
    if len(normalized_query) < 2:
        raise GeocodingError("Enter at least two characters to search for a place.")
    if not 1 <= limit <= 10:
        raise ValueError("The geocoding result limit must be between 1 and 10.")

    try:
        response = requests.get(
            NOMINATIM_SEARCH_URL,
            params={
                "q": normalized_query,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": limit,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise GeocodingError(
            "The place search service is temporarily unavailable. Try again shortly."
        ) from exc

    if not isinstance(payload, list):
        raise GeocodingError("The place search service returned an unexpected response.")

    results: list[dict[str, Any]] = []
    for item in payload:
        try:
            latitude = float(item["lat"])
            longitude = float(item["lon"])
            label = str(item["display_name"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if not label or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            continue
        results.append(
            {
                "label": label,
                "latitude": latitude,
                "longitude": longitude,
                "category": str(item.get("category", "")),
                "type": str(item.get("type", "")),
            }
        )
    return results
