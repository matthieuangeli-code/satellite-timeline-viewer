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
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
import requests


EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-c1-l2a"


class SatelliteError(RuntimeError):
    """A readable error caused by catalogue or imagery access."""


@dataclass(frozen=True)
class Scene:
    id: str
    acquired_at: str
    cloud_cover: float
    visual_href: str
    thumbnail_href: str | None = None

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
    if not 0.5 <= width_km <= 50:
        raise ValueError("La largeur doit être comprise entre 0,5 et 50 km.")
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
    )


def parse_scenes(features: list[dict[str, Any]]) -> list[Scene]:
    """Parse, sort and de-duplicate overlapping tiles from a STAC response."""
    parsed = [scene for feature in features if (scene := _scene_from_feature(feature))]
    parsed.sort(key=lambda scene: (scene.datetime, -scene.cloud_cover))
    unique: dict[str, Scene] = {}
    for scene in parsed:
        key = scene.datetime.replace(second=0, microsecond=0).isoformat()
        current = unique.get(key)
        if current is None or scene.cloud_cover < current.cloud_cover:
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
    try:
        response = requests.post(EARTH_SEARCH_URL, json=payload, timeout=45)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SatelliteError(f"Catalogue Sentinel-2 indisponible : {exc}") from exc
    scenes = parse_scenes(response.json().get("features", []))
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

    rgb = np.moveaxis(data, 0, -1)
    rgb = _to_uint8(rgb)
    output = BytesIO()
    Image.fromarray(rgb, mode="RGB").save(output, format="JPEG", quality=91)
    return output.getvalue()


def utc_today() -> date:
    return datetime.now(timezone.utc).date()

