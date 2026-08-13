"""World-wide Sentinel-2 explorer with a river-delta time-lapse mode."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
import hashlib
import importlib

import pandas as pd
import streamlit as st

from deltas import (
    DELTAS,
    DELTA_CATALOG_VERSION,
    DELTA_TYPES,
    deltas_by_type,
    type_counts,
)
from map_picker import location_picker
from movie_player import encode_frame, satellite_movie

# Streamlit can hot-reload this entrypoint while retaining an older imported
# module. The version gate picks up new image validation without reloading the
# satellite module during normal widget reruns.
import satellite as satellite_api

if getattr(satellite_api, "SATELLITE_API_VERSION", 0) < 4:
    satellite_api = importlib.reload(satellite_api)

from satellite import (
    SENTINEL2_ARCHIVE_START,
    SatelliteError,
    Scene,
    bbox_from_point,
    load_scene_png,
    search_scenes,
    utc_today,
)


st.set_page_config(
    page_title="Satellite Timeline",
    page_icon=":material/satellite_alt:",
    layout="wide",
)


@st.cache_data(ttl="30m", max_entries=40, show_spinner=False)
def cached_search(bbox, start_date, end_date, cloud_limit):
    return [
        scene.to_dict()
        for scene in search_scenes(tuple(bbox), start_date, end_date, cloud_limit)
    ]


@st.cache_data(max_entries=80, show_spinner=False)
def cached_image(scene_data, bbox, output_size=900):
    return load_scene_png(Scene.from_dict(scene_data), tuple(bbox), output_size)


@st.cache_data(max_entries=8, show_spinner=False)
def cached_movie(scene_data, bbox, output_size=720, validation_version=4):
    """Read the movie frames concurrently and retain their chronological order."""
    if validation_version != 4:
        raise ValueError("Unsupported frame validation version.")
    completed: dict[int, dict] = {}
    failures: list[str] = []

    def fetch(index, item):
        scene = Scene.from_dict(item)
        image = satellite_api.load_scene_preview_png(
            scene, tuple(bbox), output_size
        )
        return index, encode_frame(
            image,
            scene.datetime.strftime("%d %b %Y · %H:%M UTC"),
            scene.cloud_cover,
        )

    workers = min(6, max(1, len(scene_data)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch, index, item): (index, item["id"])
            for index, item in enumerate(scene_data)
        }
        for future in as_completed(futures):
            index, scene_id = futures[future]
            try:
                result_index, frame = future.result()
                completed[result_index] = frame
            except (SatelliteError, OSError, ValueError) as exc:
                failures.append(f"{scene_id}: {exc}")

    return [completed[index] for index in sorted(completed)], failures


PERIOD_OPTIONS = [180, 365, 730, 1825, 3650, "archive"]


def period_label(period: int | str) -> str:
    return {
        180: "6 months",
        365: "1 year",
        730: "2 years",
        1825: "5 years",
        3650: "10 years",
        "archive": "Full archive · since June 2015",
    }[period]


def period_start(period: int | str, end_date):
    if period == "archive":
        return SENTINEL2_ARCHIVE_START
    return max(SENTINEL2_ARCHIVE_START, end_date - timedelta(days=period))


def reset_free_explorer() -> None:
    st.session_state.free_scenes = []
    st.session_state.free_search_bbox = None
    st.session_state.pop("timeline_index", None)


@st.dialog("Confirm the exact acquisition area", width="large")
def confirm_delta_area(
    delta_name: str,
    history: int | str,
    cloud_limit: int,
) -> None:
    """Require an explicit area confirmation before any imagery is fetched."""
    delta = DELTAS[delta_name]
    if (
        st.session_state.get("pending_delta_name") != delta_name
        or st.session_state.get("pending_delta_catalog_version")
        != DELTA_CATALOG_VERSION
    ):
        st.session_state.pending_delta_name = delta_name
        st.session_state.pending_delta_catalog_version = DELTA_CATALOG_VERSION
        st.session_state.pending_delta_latitude = float(delta["latitude"])
        st.session_state.pending_delta_longitude = float(delta["longitude"])
        st.session_state.pending_delta_width = int(delta["width_km"])

    st.write(
        "Adjust the centre and width if needed. Sentinel-2 search and image "
        "downloads start only after you confirm this box."
    )
    coordinate_columns = st.columns(2)
    with coordinate_columns[0]:
        latitude = st.number_input(
            "Centre latitude",
            min_value=-89.9,
            max_value=89.9,
            step=0.001,
            format="%.4f",
            key="pending_delta_latitude",
        )
    with coordinate_columns[1]:
        longitude = st.number_input(
            "Centre longitude",
            min_value=-180.0,
            max_value=180.0,
            step=0.001,
            format="%.4f",
            key="pending_delta_longitude",
        )
    width_km = st.slider(
        "Square area width",
        min_value=4,
        max_value=80,
        step=2,
        format="%d km",
        key="pending_delta_width",
    )
    bbox = bbox_from_point(latitude, longitude, width_km)
    west, south, east, north = bbox
    st.code(
        f"West {west:.5f}  |  South {south:.5f}  |  "
        f"East {east:.5f}  |  North {north:.5f}",
        language=None,
    )
    location_picker(
        latitude,
        longitude,
        bbox,
        key=f"delta-confirm-area-{delta_name}",
        zoom=6,
        height=230,
        interactive=False,
        hint="Exact acquisition box",
    )
    if st.button(
        "Confirm area and acquire images",
        type="primary",
        icon=":material/satellite_alt:",
        width="stretch",
    ):
        zone = {
            "delta": delta_name,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "width_km": int(width_km),
            "catalog_version": DELTA_CATALOG_VERSION,
        }
        st.session_state.confirmed_delta_zone = zone
        st.session_state.delta_acquisition_request = {
            **zone,
            "history": history,
            "cloud_limit": cloud_limit,
        }
        st.rerun()


st.session_state.setdefault("location", {"lat": 48.8566, "lng": 2.3522, "zoom": 7})
st.session_state.setdefault("free_scenes", [])
st.session_state.setdefault("free_search_bbox", None)
st.session_state.setdefault("free_search_label", None)
st.session_state.setdefault("free_search_options", None)
st.session_state.setdefault("movie_frames", [])
st.session_state.setdefault("movie_meta", None)
st.session_state.setdefault("confirmed_delta_zone", None)
st.session_state.setdefault("delta_acquisition_request", None)

st.title("Satellite Timeline")
st.caption("Explore how coastlines, wetlands and river channels change through time.")
st.markdown(
    ":green-badge[No API key] :blue-badge[Sentinel-2 L2A] "
    ":gray-badge[Natural colour · 10 m]"
)

mode = st.segmented_control(
    "Explorer mode",
    ["Delta movie", "Anywhere on Earth"],
    default="Delta movie",
)

if mode == "Delta movie":
    player_column, context_column = st.columns(
        [3.45, 1.0], gap="medium", vertical_alignment="top"
    )

    with context_column.container(border=True):
        st.subheader("Delta selection", anchor=False)
        counts = type_counts()
        delta_type = st.selectbox(
            "Dominant process",
            options=DELTA_TYPES,
            format_func=lambda value: f"{value} ({counts[value]})",
        )
        delta_name = st.selectbox(
            "River delta",
            options=deltas_by_type(delta_type),
        )
        history = st.selectbox(
            "Time span",
            options=PERIOD_OPTIONS,
            index=1,
            format_func=period_label,
        )
        st.caption("Sentinel-2 archive available from 27 June 2015 to today.")
        cloud_limit = st.slider(
            "Maximum catalogue cloud",
            5,
            80,
            20,
            5,
            format="%d %%",
            help="Every acquisition below this threshold is included when its image can be read.",
        )
        define_area_clicked = st.button(
            "Define area and create movie",
            type="primary",
            icon=":material/crop_free:",
            width="stretch",
        )

    delta = DELTAS[delta_name]
    confirmed_zone = st.session_state.confirmed_delta_zone
    if (
        not confirmed_zone
        or confirmed_zone["delta"] != delta_name
        or confirmed_zone.get("catalog_version") != DELTA_CATALOG_VERSION
    ):
        confirmed_zone = {
            "delta": delta_name,
            "latitude": float(delta["latitude"]),
            "longitude": float(delta["longitude"]),
            "width_km": int(delta["width_km"]),
            "catalog_version": DELTA_CATALOG_VERSION,
        }
    bbox = bbox_from_point(
        confirmed_zone["latitude"],
        confirmed_zone["longitude"],
        confirmed_zone["width_km"],
    )
    request_signature = [
        delta_name,
        history,
        cloud_limit,
        round(confirmed_zone["latitude"], 5),
        round(confirmed_zone["longitude"], 5),
        confirmed_zone["width_km"],
    ]

    with context_column:
        location_picker(
            confirmed_zone["latitude"],
            confirmed_zone["longitude"],
            bbox,
            key=f"delta-overview-area-{delta_name}",
            zoom=5,
            height=160,
            interactive=False,
            hint="Selected acquisition area",
        )
        st.caption(
            f"{confirmed_zone['latitude']:.4f}, {confirmed_zone['longitude']:.4f} · "
            f"{confirmed_zone['width_km']} × {confirmed_zone['width_km']} km"
        )
        st.caption(delta["description"])

    with player_column:
        st.subheader(delta_name, anchor=False)
        st.caption(
            f"{delta['type']} · 30-delta catalogue · black and incomplete frames "
            "are rejected automatically"
        )
        player_status = st.container()
        movie_slot = st.container()

    if define_area_clicked:
        confirm_delta_area(delta_name, history, cloud_limit)

    acquisition_request = st.session_state.pop("delta_acquisition_request", None)
    if acquisition_request:
        confirmed_zone = acquisition_request
        bbox = bbox_from_point(
            confirmed_zone["latitude"],
            confirmed_zone["longitude"],
            confirmed_zone["width_km"],
        )
        request_signature = [
            delta_name,
            history,
            cloud_limit,
            round(confirmed_zone["latitude"], 5),
            round(confirmed_zone["longitude"], 5),
            confirmed_zone["width_km"],
        ]
        end_date = utc_today()
        start_date = period_start(history, end_date)
        build_status = None
        try:
            with player_status.status(
                "Building the Sentinel-2 movie…", expanded=True
            ) as status:
                build_status = status
                status.write("Searching the public catalogue…")
                scene_data = cached_search(bbox, start_date, end_date, cloud_limit)
                if not scene_data:
                    raise SatelliteError(
                        "No Sentinel-2 acquisitions match this period and cloud threshold."
                    )
                status.write(
                    f"Reading {len(scene_data)} real satellite acquisitions…"
                )
                frames, failures = cached_movie(scene_data, bbox)
                if not frames:
                    incomplete_count = sum(
                        "black or incomplete" in failure.lower()
                        for failure in failures
                    )
                    if incomplete_count == len(failures):
                        raise SatelliteError(
                            "The selected square crosses the usable edge of a Sentinel-2 "
                            "tile. Define the area again, then shift its centre or reduce "
                            "its width. No incomplete image was added to the movie."
                        )
                    raise SatelliteError("None of the matching images could be read.")
                st.session_state.movie_frames = frames
                st.session_state.movie_meta = {
                    "request": request_signature,
                    "delta": delta_name,
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "catalogue_count": len(scene_data),
                    "failures": failures,
                    "zone": confirmed_zone,
                }
                status.update(
                    label=f"Movie ready · {len(frames)} frames",
                    state="complete",
                    expanded=False,
                )
        except SatelliteError as exc:
            if build_status is not None:
                build_status.update(
                    label="Movie could not be built",
                    state="error",
                    expanded=False,
                )
            movie_slot.error(str(exc), icon=":material/error:")

    movie_meta = st.session_state.movie_meta
    if movie_meta and "zone" not in movie_meta:
        st.session_state.movie_meta = None
        st.session_state.movie_frames = []
        movie_meta = None
    if movie_meta and movie_meta["request"] != request_signature:
        st.info(
            "The settings changed. Define and confirm the exact area to build the new sequence.",
            icon=":material/info:",
        )
    elif movie_meta and st.session_state.movie_frames:
        frames = st.session_state.movie_frames
        movie_id = hashlib.sha256(
            "|".join(map(str, movie_meta["request"])).encode()
        ).hexdigest()[:12]
        movie_slot.caption(
            f"{len(frames)} frames · {movie_meta['start']} → {movie_meta['end']} · "
            f"exact area {movie_meta['zone']['width_km']} × "
            f"{movie_meta['zone']['width_km']} km"
        )
        with movie_slot:
            satellite_movie(
                frames,
                movie_id=movie_id,
                key=f"delta-movie-{movie_id}",
            )
        failed_count = len(movie_meta["failures"])
        if failed_count:
            black_count = sum(
                "black" in failure.lower() for failure in movie_meta["failures"]
            )
            movie_slot.warning(
                f"{failed_count} of {movie_meta['catalogue_count']} catalogue acquisitions "
                f"were omitted, including {black_count} black or incomplete frames.",
                icon=":material/broken_image:",
            )
        movie_slot.caption(
            "Frames are real acquisitions in chronological order. Apparent motion may also "
            "reflect tides, seasons, clouds, haze or different sun angles."
        )
    else:
        with movie_slot.container(border=True):
            st.subheader("Ready to animate", anchor=False)
            st.write(
                "Choose one of the 30 classified deltas, then define and confirm the exact "
                "acquisition area. The complete player will appear here without an internal "
                "scrolling window."
            )
    st.stop()


with st.sidebar:
    st.header("Area and period", anchor=False)
    width_km = st.slider(
        "Area width",
        1,
        30,
        5,
        1,
        format="%d km",
        help="The displayed image is a square centred on the marker.",
    )
    history = st.selectbox(
        "History to load",
        options=PERIOD_OPTIONS,
        index=1,
        format_func=period_label,
    )
    cloud_limit = st.slider(
        "Maximum catalogue cloud",
        5,
        100,
        60,
        5,
        format="%d %%",
    )
    load_clicked = st.button(
        "Load images for this area",
        type="primary",
        icon=":material/travel_explore:",
        width="stretch",
    )

current_options = [width_km, history, cloud_limit]
if (
    st.session_state.free_scenes
    and st.session_state.free_search_options is not None
    and st.session_state.free_search_options != current_options
):
    reset_free_explorer()

location = st.session_state.location
bbox = bbox_from_point(location["lat"], location["lng"], width_km)
map_result = location_picker(
    location["lat"],
    location["lng"],
    bbox,
    key="world-map",
    zoom=int(location.get("zoom", 7)),
)
picked = getattr(map_result, "selection", None)
if picked:
    next_location = {
        "lat": round(float(picked["lat"]), 6),
        "lng": round(float(picked["lng"]), 6),
        "zoom": int(picked.get("zoom", location.get("zoom", 7))),
    }
    if (
        next_location["lat"] != location["lat"]
        or next_location["lng"] != location["lng"]
    ):
        st.session_state.location = next_location
        reset_free_explorer()
        st.rerun()

with st.container(horizontal=True):
    st.metric("Latitude", f"{location['lat']:.5f}", border=True)
    st.metric("Longitude", f"{location['lng']:.5f}", border=True)
    st.metric("Area", f"{width_km} × {width_km} km", border=True)

result_slot = st.container()
if load_clicked:
    end_date = utc_today()
    start_date = period_start(history, end_date)
    try:
        with st.status("Searching Sentinel-2 acquisitions…", expanded=True) as status:
            scene_data = cached_search(bbox, start_date, end_date, cloud_limit)
            st.session_state.free_scenes = scene_data
            st.session_state.free_search_bbox = list(bbox)
            st.session_state.free_search_options = current_options
            st.session_state.free_search_label = (
                f"{start_date:%d/%m/%Y} → {end_date:%d/%m/%Y} · cloud ≤ {cloud_limit}%"
            )
            st.session_state.pop("timeline_index", None)
            status.update(
                label=f"{len(scene_data)} acquisition(s) found",
                state="complete",
                expanded=False,
            )
    except SatelliteError as exc:
        result_slot.error(str(exc), icon=":material/error:")

scene_data = st.session_state.free_scenes
if not scene_data:
    with result_slot.container(border=True):
        st.subheader("Ready to explore", anchor=False)
        st.write(
            "Click the map, adjust the area size and use **Load images for this area**."
        )
    st.stop()

scenes = [Scene.from_dict(item) for item in scene_data]
search_bbox = tuple(st.session_state.free_search_bbox)
latest = scenes[-1]
result_slot.subheader("Available images", anchor=False)
result_slot.caption(
    f"{len(scenes)} acquisitions · {st.session_state.free_search_label} · "
    f"latest image {latest.datetime:%d/%m/%Y}"
)

indices = list(range(len(scenes)))
selected_index = result_slot.select_slider(
    "Timeline",
    options=indices,
    value=indices[-1],
    format_func=lambda index: (
        f"{scenes[index].datetime:%d/%m/%Y} · {scenes[index].cloud_cover:.0f}%"
    ),
    key="timeline_index",
)
selected = scenes[selected_index]
with result_slot.container(horizontal=True):
    st.metric("Date", f"{selected.datetime:%d/%m/%Y}", border=True)
    st.metric("UTC time", f"{selected.datetime:%H:%M}", border=True)
    st.metric("Catalogue cloud", f"{selected.cloud_cover:.1f}%", border=True)
    st.metric("Series position", f"{selected_index + 1} / {len(scenes)}", border=True)

try:
    with result_slot.skeleton():
        image = cached_image(selected.to_dict(), search_bbox)
        result_slot.image(
            image,
            width="stretch",
            caption=f"Sentinel-2 · {selected.datetime:%d/%m/%Y at %H:%M UTC}",
        )
except SatelliteError as exc:
    result_slot.error(str(exc), icon=":material/broken_image:")
