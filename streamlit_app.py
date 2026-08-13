"""Personal world-wide Sentinel-2 image timeline."""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from map_picker import location_picker
from satellite import (
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


@st.cache_data(max_entries=60, show_spinner=False)
def cached_image(scene_data, bbox):
    return load_scene_png(Scene.from_dict(scene_data), tuple(bbox))


st.session_state.setdefault("location", {"lat": 48.8566, "lng": 2.3522, "zoom": 7})
st.session_state.setdefault("scenes", [])
st.session_state.setdefault("search_bbox", None)
st.session_state.setdefault("search_label", None)
st.session_state.setdefault("search_options", None)

st.title("Satellite Timeline")
st.caption(
    "Choisissez un point sur Terre et parcourez les acquisitions publiques Sentinel-2."
)
st.markdown(
    ":green-badge[Sans clé API] :blue-badge[Sentinel-2 L2A] "
    ":gray-badge[Couleur naturelle · 10 m]"
)

with st.sidebar:
    st.header("Zone et période", anchor=False)
    width_km = st.slider(
        "Largeur de la zone",
        1,
        30,
        5,
        1,
        format="%d km",
        help="La photo affichée est un carré centré sur le marqueur.",
    )
    history = st.selectbox(
        "Historique à charger",
        options=[180, 365, 730],
        index=1,
        format_func=lambda days: {180: "6 mois", 365: "1 an", 730: "2 ans"}[days],
    )
    cloud_limit = st.slider(
        "Nébulosité maximale de la tuile",
        5,
        100,
        60,
        5,
        format="%d %%",
        help="La valeur catalogue concerne toute la tuile, pas uniquement le carré affiché.",
    )
    load_clicked = st.button(
        "Charger les photos de cette zone",
        type="primary",
        icon=":material/travel_explore:",
        width="stretch",
    )

current_options = [width_km, history, cloud_limit]
if (
    st.session_state.scenes
    and st.session_state.search_options is not None
    and st.session_state.search_options != current_options
):
    st.session_state.scenes = []
    st.session_state.search_bbox = None
    st.session_state.pop("timeline_index", None)

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
        st.session_state.scenes = []
        st.session_state.search_bbox = None
        st.session_state.pop("timeline_index", None)
        st.rerun()

with st.container(horizontal=True):
    st.metric("Latitude", f"{location['lat']:.5f}", border=True)
    st.metric("Longitude", f"{location['lng']:.5f}", border=True)
    st.metric("Emprise", f"{width_km} × {width_km} km", border=True)

result_slot = st.container()

if load_clicked:
    end_date = utc_today()
    start_date = end_date - timedelta(days=history)
    try:
        with st.status("Recherche des acquisitions Sentinel-2…", expanded=True) as status:
            st.write(f"Période : {start_date:%d/%m/%Y} → {end_date:%d/%m/%Y}")
            scene_data = cached_search(bbox, start_date, end_date, cloud_limit)
            st.session_state.scenes = scene_data
            st.session_state.search_bbox = list(bbox)
            st.session_state.search_options = current_options
            st.session_state.search_label = (
                f"{start_date:%d/%m/%Y} → {end_date:%d/%m/%Y} · nuages ≤ {cloud_limit} %"
            )
            st.session_state.pop("timeline_index", None)
            status.update(
                label=f"{len(scene_data)} acquisition(s) trouvée(s)",
                state="complete",
                expanded=False,
            )
    except SatelliteError as exc:
        result_slot.error(str(exc), icon=":material/error:")

scene_data = st.session_state.scenes
if not scene_data:
    with result_slot.container(border=True):
        st.subheader("Prêt à explorer", anchor=False)
        st.write(
            "Cliquez sur la carte, ajustez la taille de la zone puis utilisez le bouton "
            "**Charger les photos de cette zone**."
        )
    st.stop()

scenes = [Scene.from_dict(item) for item in scene_data]
search_bbox = tuple(st.session_state.search_bbox)
latest = scenes[-1]

result_slot.subheader("Photos disponibles", anchor=False)
result_slot.caption(
    f"{len(scenes)} acquisitions · {st.session_state.search_label} · "
    f"dernière image {latest.datetime:%d/%m/%Y}"
)

indices = list(range(len(scenes)))
selected_index = result_slot.select_slider(
    "Curseur temporel",
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
    st.metric("Heure UTC", f"{selected.datetime:%H:%M}", border=True)
    st.metric("Nuages catalogue", f"{selected.cloud_cover:.1f} %", border=True)
    st.metric(
        "Position dans la série",
        f"{selected_index + 1} / {len(scenes)}",
        border=True,
    )

try:
    with result_slot.skeleton():
        image = cached_image(selected.to_dict(), search_bbox)
        result_slot.image(
            image,
            width="stretch",
            caption=(
                f"Sentinel-2 · {selected.datetime:%d/%m/%Y à %H:%M UTC} · "
                f"zone {width_km} × {width_km} km"
            ),
        )
except SatelliteError as exc:
    result_slot.error(str(exc), icon=":material/broken_image:")

result_slot.caption(
    "Sentinel-2 revisite généralement une zone tous les quelques jours. La dernière "
    "acquisition peut contenir des nuages ; réduisez le seuil si nécessaire."
)
