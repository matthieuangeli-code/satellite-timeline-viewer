"""Clickable world map implemented with a Streamlit Custom Component v2."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st


_MAP_HTML = """
<div class="map-shell">
  <div id="geo-map" aria-label="Carte mondiale interactive"></div>
  <div class="map-hint">Cliquez sur la carte pour déplacer la zone d’observation.</div>
</div>
"""

_MAP_CSS = """
.map-shell {
  position: relative;
  width: 100%;
  min-height: 460px;
  overflow: hidden;
  border: 1px solid var(--st-border-color, #334247);
  border-radius: var(--st-base-radius, 12px);
  background: var(--st-secondary-background-color, #152125);
}
#geo-map {
  width: 100%;
  height: 460px;
  background: #dce8e5;
}
.map-hint {
  position: absolute;
  z-index: 1000;
  left: 12px;
  bottom: 12px;
  padding: 7px 10px;
  border-radius: 8px;
  color: #10211d;
  background: rgba(255, 255, 255, 0.92);
  font: 600 12px/1.3 var(--st-font, sans-serif);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.18);
  pointer-events: none;
}
"""

_MAP_JS = """
const mapInstances = new WeakMap()

function ensureLeaflet() {
  if (window.L) return Promise.resolve(window.L)
  if (window.__satelliteTimelineLeaflet) return window.__satelliteTimelineLeaflet

  window.__satelliteTimelineLeaflet = new Promise((resolve, reject) => {
    if (!document.querySelector('link[data-satellite-leaflet]')) {
      const link = document.createElement('link')
      link.rel = 'stylesheet'
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
      link.dataset.satelliteLeaflet = 'true'
      document.head.appendChild(link)
    }
    const script = document.createElement('script')
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
    script.crossOrigin = 'anonymous'
    script.onload = () => resolve(window.L)
    script.onerror = () => reject(new Error('Impossible de charger Leaflet'))
    document.head.appendChild(script)
  })
  return window.__satelliteTimelineLeaflet
}

function changed(a, b) {
  return !a || Math.abs(a.lat - b.lat) > 1e-7 || Math.abs(a.lng - b.lng) > 1e-7
}

export default async function(component) {
  const { data, parentElement, setStateValue, setTriggerValue } = component
  const L = await ensureLeaflet()
  const target = parentElement.querySelector('#geo-map')
  if (!target) return

  const selection = {
    lat: Number(data.latitude),
    lng: Number(data.longitude),
  }
  let state = mapInstances.get(parentElement)

  if (!state) {
    const map = L.map(target, { zoomControl: true, worldCopyJump: true })
      .setView([selection.lat, selection.lng], Number(data.zoom || 5))
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map)
    const marker = L.circleMarker([selection.lat, selection.lng], {
      radius: 7,
      color: '#0d5e4d',
      weight: 3,
      fillColor: '#4fc3a1',
      fillOpacity: 1,
    }).addTo(map)
    const rectangle = L.rectangle(data.bounds, {
      color: '#0d5e4d',
      weight: 2,
      fillColor: '#4fc3a1',
      fillOpacity: 0.12,
    }).addTo(map)

    state = { map, marker, rectangle, selection }
    mapInstances.set(parentElement, state)

    map.on('click', event => {
      const picked = {
        lat: Number(event.latlng.lat.toFixed(6)),
        lng: Number(event.latlng.lng.toFixed(6)),
        zoom: map.getZoom(),
      }
      state.selection = picked
      marker.setLatLng([picked.lat, picked.lng])
      setStateValue('selection', picked)
      setTriggerValue('picked', picked)
    })
    setTimeout(() => map.invalidateSize(), 0)
  }

  if (changed(state.selection, selection)) {
    state.selection = selection
    state.marker.setLatLng([selection.lat, selection.lng])
    state.map.panTo([selection.lat, selection.lng], { animate: false })
  }
  state.rectangle.setBounds(data.bounds)
}
"""


_WORLD_MAP = st.components.v2.component(
    "satellite_location_picker",
    html=_MAP_HTML,
    css=_MAP_CSS,
    js=_MAP_JS,
    isolate_styles=False,
)


def location_picker(
    latitude: float,
    longitude: float,
    bounds: tuple[float, float, float, float],
    *,
    key: str,
    zoom: int = 5,
    on_selection_change: Callable[[], None] | None = None,
):
    """Mount the map and return a result containing ``selection`` and ``picked``."""
    if on_selection_change is None:
        on_selection_change = lambda: None
    west, south, east, north = bounds
    return _WORLD_MAP(
        key=key,
        data={
            "latitude": latitude,
            "longitude": longitude,
            "zoom": zoom,
            "bounds": [[south, west], [north, east]],
        },
        default={
            "selection": {"lat": latitude, "lng": longitude, "zoom": zoom}
        },
        on_selection_change=on_selection_change,
        on_picked_change=lambda: None,
        width="stretch",
        height=460,
    )

