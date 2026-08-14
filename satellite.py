"""Small Sentinel-2 catalogue and COG reader for a point-centred timeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from io import BytesIO
import math
import time
from typing import Any

import numpy as np
from PIL import Image
import rasterio
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.warp import reproject
import requests


EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-c1-l2a"
SATELLITE_API_VERSION = 5
SENTINEL2_ARCHIVE_START = date(2015, 6, 27)
MAX_AREA_WIDTH_KM = 500
CATALOGUE_PAGE_SIZE = 100
CATALOGUE_ATTEMPTS = 4


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
    visual_hrefs: tuple[str, ...] = ()
    preview_hrefs: tuple[str, ...] = ()

    @property
    def datetime(self) -> datetime:
        return datetime.fromisoformat(self.acquired_at.replace("Z", "+00:00"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Scene":
        normalized = dict(value)
        normalized["visual_hrefs"] = tuple(normalized.get("visual_hrefs", ()))
        normalized["preview_hrefs"] = tuple(normalized.get("preview_hrefs", ()))
        return cls(**normalized)


def bbox_from_point(
    latitude: float, longitude: float, width_km: float
) -> tuple[float, float, float, float]:
    """Return a WGS84 square around a point, safely clamped to the globe."""
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Coordonnées hors limites.")
    if not 0.5 <= width_km <= MAX_AREA_WIDTH_KM:
        raise ValueError(
            f"La largeur doit être comprise entre 0,5 et {MAX_AREA_WIDTH_KM} km."
        )
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
        visual_hrefs=(visual,),
        preview_hrefs=(
            (assets["preview"]["href"],)
            if assets.get("preview", {}).get("href")
            else ()
        ),
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
    grouped: dict[str, list[Scene]] = {}
    for scene in parsed:
        key = scene.datetime.replace(second=0, microsecond=0).isoformat()
        grouped.setdefault(key, []).append(scene)

    mosaics: list[Scene] = []
    for candidates in grouped.values():
        ordered = sorted(
            candidates,
            key=lambda scene: (
                -_intersection_area(scene.bounds, target_bbox),
                scene.cloud_cover,
            ),
        )
        chosen = ordered[0]
        intersecting = [
            scene
            for scene in ordered
            if target_bbox is None
            or _intersection_area(scene.bounds, target_bbox) > 0
        ] or [chosen]
        visual_hrefs = tuple(
            dict.fromkeys(scene.visual_href for scene in intersecting)
        )
        preview_hrefs = tuple(
            dict.fromkeys(
                scene.preview_href
                for scene in intersecting
                if scene.preview_href is not None
            )
        )
        mosaics.append(
            replace(
                chosen,
                visual_hrefs=visual_hrefs,
                preview_hrefs=preview_hrefs,
            )
        )
    return sorted(mosaics, key=lambda scene: scene.datetime)


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
        # Smaller pages put less pressure on the public catalogue for large
        # areas and long time ranges, which reduces transient HTTP 500 errors.
        "limit": CATALOGUE_PAGE_SIZE,
        "query": {"eo:cloud_cover": {"lte": cloud_limit}},
    }
    features: list[dict[str, Any]] = []
    request_url = EARTH_SEARCH_URL
    request_method = "POST"
    request_body: dict[str, Any] | None = payload
    try:
        for _page in range(50):
            response = _request_catalogue_page(
                request_url, request_method, request_body
            )
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


def _request_catalogue_page(
    url: str,
    method: str,
    body: dict[str, Any] | None,
):
    """Read one STAC page and retry transient public-service failures."""
    last_error: requests.RequestException | None = None
    for attempt in range(CATALOGUE_ATTEMPTS):
        try:
            if method == "POST":
                response = requests.post(url, json=body, timeout=(10, 60))
            else:
                response = requests.get(url, timeout=(10, 60))
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            retryable = status is None or status == 429 or status >= 500
            if not retryable or attempt == CATALOGUE_ATTEMPTS - 1:
                raise
            time.sleep(0.6 * (2**attempt))
    raise last_error  # pragma: no cover - the loop always returns or raises


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


def _add_source_to_mosaic(
    source,
    mosaic: np.ndarray,
    bbox: tuple[float, float, float, float],
) -> None:
    """Reproject one Sentinel tile and fill only gaps in the shared mosaic."""
    output_size = mosaic.shape[1]
    destination_transform = transform_from_bounds(
        *bbox, width=output_size, height=output_size
    )
    tile = np.zeros_like(mosaic)
    for band_index in range(3):
        reproject(
            source=rasterio.band(source, band_index + 1),
            destination=tile[band_index],
            src_transform=source.transform,
            src_crs=source.crs,
            dst_transform=destination_transform,
            dst_crs="EPSG:4326",
            src_nodata=source.nodata,
            dst_nodata=0,
            resampling=Resampling.bilinear,
        )
    tile_coverage = np.any(np.abs(tile) > 1e-6, axis=0)
    mosaic_empty = ~np.any(np.abs(mosaic) > 1e-6, axis=0)
    fill = tile_coverage & mosaic_empty
    mosaic[:, fill] = tile[:, fill]


def _scene_visual_hrefs(scene: Scene) -> tuple[str, ...]:
    return scene.visual_hrefs or (scene.visual_href,)


def _scene_preview_hrefs(scene: Scene) -> tuple[str, ...]:
    if scene.preview_hrefs:
        return scene.preview_hrefs
    return (scene.preview_href,) if scene.preview_href else ()


def load_scene_png(
    scene: Scene,
    bbox: tuple[float, float, float, float],
    output_size: int = 900,
) -> bytes:
    """Mosaic every intersecting true-colour COG over the exact selected AOI."""
    mosaic = np.zeros((3, output_size, output_size), dtype=np.float32)
    failures: list[str] = []
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS="TIF,tif",
        GDAL_HTTP_MULTIRANGE="YES",
        GDAL_HTTP_CONNECTTIMEOUT="10",
        GDAL_HTTP_TIMEOUT="45",
    ):
        for href in _scene_visual_hrefs(scene):
            try:
                with rasterio.open(href) as source:
                    _add_source_to_mosaic(source, mosaic, bbox)
            except (OSError, rasterio.errors.RasterioError) as exc:
                failures.append(str(exc))
    if not np.any(mosaic):
        detail = failures[0] if failures else "no readable intersecting tile"
        raise SatelliteError(f"Image Sentinel-2 illisible : {detail}")

    rgb = _validated_rgb(mosaic)
    output = BytesIO()
    Image.fromarray(rgb, mode="RGB").save(output, format="JPEG", quality=91)
    return output.getvalue()


def load_scene_preview_png(
    scene: Scene,
    bbox: tuple[float, float, float, float],
    output_size: int = 720,
) -> bytes:
    """Mosaic georeferenced previews from every tile crossing the selected AOI."""
    preview_hrefs = _scene_preview_hrefs(scene)
    if not preview_hrefs:
        return load_scene_png(scene, bbox, output_size)
    mosaic = np.zeros((3, output_size, output_size), dtype=np.float32)
    failures: list[str] = []
    for href in preview_hrefs:
        try:
            response = requests.get(href, timeout=(10, 30))
            response.raise_for_status()
            with MemoryFile(response.content) as memory_file:
                with memory_file.open() as source:
                    _add_source_to_mosaic(source, mosaic, bbox)
        except (
            requests.RequestException,
            OSError,
            rasterio.errors.RasterioError,
        ) as exc:
            failures.append(str(exc))
    if not np.any(mosaic):
        detail = failures[0] if failures else "no readable intersecting tile"
        raise SatelliteError(f"Aperçu Sentinel-2 illisible : {detail}")

    rgb = _validated_rgb(mosaic)
    output = BytesIO()
    Image.fromarray(rgb, mode="RGB").save(output, format="JPEG", quality=88)
    return output.getvalue()


def utc_today() -> date:
    return datetime.now(timezone.utc).date()
