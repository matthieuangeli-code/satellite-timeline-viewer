"""Small Sentinel-2 catalogue and COG reader for a point-centred timeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from io import BytesIO
import math
from typing import Any

import numpy as np
from PIL import Image
import rasterio
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
import requests


EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-c1-l2a"
SATELLITE_API_VERSION = 3
SENTINEL2_ARCHIVE_START = date(2015, 6, 27)


class SatelliteError(RuntimeError):
    """A readable error caused by catalogue or imagery access."""


@dataclass(frozen=True)
class Scene:
    id: str
    acquired_at: str
    cloud_cover: float
    visual_href: str
    thumbnail_href: str | None = None
    preview_href: str | None = None
    bounds: tuple[float, float, float, float] | None = None

    @property
    def datetime(self) -> datetime:
        return datetime.fromisoformat(self.acquired_at.replace("Z", "+00:00"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Scene":
        return cls(**value)


def bbox_from_point(
    latitude: float, longitude: float, width_km: float
) -> tuple[float, float, float, float]:
    """Return a WGS84 square around a point, safely clamped to the globe."""
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Coordonnées hors limites.")
    if not 0.5 <= width_km <= 80:
        raise ValueError("La largeur doit être comprise entre 0,5 et 80 km.")
    half_lat = width_km / 2 / 110.574
    cos_lat = max(math.cos(math.radians(latitude)), 0.05)
    half_lon = width_km / 2 / (111.320 * cos_lat)
    return (
        max(-180.0, longitude - half_lon),
        max(-89.999, latitude - half_lat),
        min(180.0, longitude + half_lon),
        min(89.999, latitude + half_lat),
    )


def _scene_from_feature(feature: dict[str, Any]) -> Scene | None:
    assets = feature.get("assets", {})
    visual = assets.get("visual", {}).get("href")
    acquired = feature.get("properties", {}).get("datetime")
    if not visual or not acquired:
        return None
    return Scene(
        id=feature["id"],
        acquired_at=acquired,
        cloud_cover=float(feature.get("properties", {}).get("eo:cloud_cover") or 0),
        visual_href=visual,
        thumbnail_href=assets.get("thumbnail", {}).get("href"),
        preview_href=assets.get("preview", {}).get("href"),
        bounds=(tuple(feature["bbox"]) if feature.get("bbox") else None),
    )


def _intersection_area(
    first: tuple[float, float, float, float] | None,
    second: tuple[float, float, float, float] | None,
) -> float:
    if first is None or second is None:
        return 0.0
    west = max(first[0], second[0])
    south = max(first[1], second[1])
    east = min(first[2], second[2])
    north = min(first[3], second[3])
    return max(0.0, east - west) * max(0.0, north - south)


def parse_scenes(
    features: list[dict[str, Any]],
    target_bbox: tuple[float, float, float, float] | None = None,
) -> list[Scene]:
    """Parse, sort and de-duplicate overlapping tiles from a STAC response."""
    parsed = [scene for feature in features if (scene := _scene_from_feature(feature))]
    parsed.sort(key=lambda scene: (scene.datetime, -scene.cloud_cover))
    unique: dict[str, Scene] = {}
    for scene in parsed:
        key = scene.datetime.replace(second=0, microsecond=0).isoformat()
        current = unique.get(key)
        scene_coverage = _intersection_area(scene.bounds, target_bbox)
        current_coverage = _intersection_area(current.bounds, target_bbox) if current else -1
        if (
            current is None
            or scene_coverage > current_coverage
            or (
                scene_coverage == current_coverage
                and scene.cloud_cover < current.cloud_cover
            )
        ):
            unique[key] = scene
    return sorted(unique.values(), key=lambda scene: scene.datetime)


def search_scenes(
    bbox: tuple[float, float, float, float],
    start_date: date,
    end_date: date,
    cloud_limit: int,
) -> list[Scene]:
    """Return all available Sentinel-2 acquisitions within the chosen window."""
    if start_date > end_date:
        raise ValueError("La date de début doit précéder la date de fin.")
    payload = {
        "collections": [COLLECTION],
        "bbox": list(bbox),
        "datetime": f"{start_date.isoformat()}T00:00:00Z/{end_date.isoformat()}T23:59:59Z",
        "limit": 200,
        "query": {"eo:cloud_cover": {"lte": cloud_limit}},
    }
    features: list[dict[str, Any]] = []
    request_url = EARTH_SEARCH_URL
    request_method = "POST"
    request_body: dict[str, Any] | None = payload
    try:
        for _page in range(50):
            if request_method == "POST":
                response = requests.post(
                    request_url, json=request_body, timeout=45
                )
            else:
                response = requests.get(request_url, timeout=45)
            response.raise_for_status()
            page = response.json()
            features.extend(page.get("features", []))

            next_link = next(
                (link for link in page.get("links", []) if link.get("rel") == "next"),
                None,
            )
            if not next_link:
                break
            request_url = next_link["href"]
            request_method = next_link.get("method", "GET").upper()
            request_body = next_link.get("body")
        else:
            raise SatelliteError(
                "The catalogue returned too many pages for one request. "
                "Reduce the period or cloud threshold."
            )
    except requests.RequestException as exc:
        raise SatelliteError(f"Catalogue Sentinel-2 indisponible : {exc}") from exc
    scenes = parse_scenes(features, bbox)
    return [scene for scene in scenes if scene.cloud_cover <= cloud_limit]


def _to_uint8(rgb: np.ndarray) -> np.ndarray:
    if rgb.dtype == np.uint8:
        return rgb
    finite = np.isfinite(rgb)
    if not finite.any():
        return np.zeros(rgb.shape, dtype=np.uint8)
    values = rgb[finite]
    low, high = np.percentile(values, [2, 98])
    if high <= low:
        return np.zeros(rgb.shape, dtype=np.uint8)
    return np.clip((rgb - low) / (high - low) * 255, 0, 255).astype(np.uint8)


def _validated_rgb(data: np.ndarray) -> np.ndarray:
    """Convert a raster crop to RGB and reject blank or black acquisitions."""
    if data.ndim != 3 or data.shape[0] != 3:
        raise SatelliteError("The satellite image does not contain three colour bands.")

    raw_rgb = np.moveaxis(data, 0, -1)
    finite = np.all(np.isfinite(raw_rgb), axis=-1)
    nonzero = np.any(np.abs(raw_rgb) > 1e-6, axis=-1)
    covered_fraction = float(np.mean(finite & nonzero))

    # Boundless reads are padded with zeros. A visible black strip therefore
    # means the selected tile does not cover the requested area completely.
    if covered_fraction < 0.995:
        raise SatelliteError(
            "Black or incomplete image rejected: the acquisition does not cover "
            "the exact selected area."
        )

    rgb = _to_uint8(raw_rgb)
    luminance = (
        0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    )
    dark_fraction = float(np.mean(luminance <= 4))
    contrast = float(np.percentile(luminance, 98) - np.percentile(luminance, 2))
    if dark_fraction > 0.90 or contrast < 3:
        raise SatelliteError("Black or blank satellite image rejected automatically.")
    return rgb


def load_scene_png(
    scene: Scene,
    bbox: tuple[float, float, float, float],
    output_size: int = 900,
) -> bytes:
    """Read only the selected AOI from the public true-colour COG."""
    try:
        with rasterio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS="TIF,tif",
            GDAL_HTTP_MULTIRANGE="YES",
            GDAL_HTTP_CONNECTTIMEOUT="10",
            GDAL_HTTP_TIMEOUT="45",
        ):
            with rasterio.open(scene.visual_href) as source:
                projected = transform_bounds(
                    "EPSG:4326", source.crs, *bbox, densify_pts=21
                )
                window = from_bounds(*projected, transform=source.transform)
                data = source.read(
                    indexes=(1, 2, 3),
                    window=window,
                    out_shape=(3, output_size, output_size),
                    resampling=Resampling.bilinear,
                    boundless=True,
                    fill_value=0,
                )
    except (OSError, rasterio.errors.RasterioError) as exc:
        raise SatelliteError(f"Image Sentinel-2 illisible : {exc}") from exc

    rgb = _validated_rgb(data)
    output = BytesIO()
    Image.fromarray(rgb, mode="RGB").save(output, format="JPEG", quality=91)
    return output.getvalue()


def load_scene_preview_png(
    scene: Scene,
    bbox: tuple[float, float, float, float],
    output_size: int = 720,
) -> bytes:
    """Download the small georeferenced preview and crop it for fast movies."""
    if not scene.preview_href:
        return load_scene_png(scene, bbox, output_size)
    try:
        response = requests.get(scene.preview_href, timeout=(10, 30))
        response.raise_for_status()
        with MemoryFile(response.content) as memory_file:
            with memory_file.open() as source:
                projected = transform_bounds(
                    "EPSG:4326", source.crs, *bbox, densify_pts=21
                )
                window = from_bounds(*projected, transform=source.transform)
                data = source.read(
                    indexes=(1, 2, 3),
                    window=window,
                    out_shape=(3, output_size, output_size),
                    resampling=Resampling.bilinear,
                    boundless=True,
                    fill_value=0,
                )
    except (requests.RequestException, OSError, rasterio.errors.RasterioError) as exc:
        raise SatelliteError(f"Aperçu Sentinel-2 illisible : {exc}") from exc

    rgb = _validated_rgb(data)
    output = BytesIO()
    Image.fromarray(rgb, mode="RGB").save(output, format="JPEG", quality=88)
    return output.getvalue()


def utc_today() -> date:
    return datetime.now(timezone.utc).date()
