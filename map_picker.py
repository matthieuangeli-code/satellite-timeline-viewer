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
  height: 100%;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--st-border-color, #334247);
  border-radius: var(--st-base-radius, 12px);
  background: var(--st-secondary-background-color, #152125);
}
#geo-map {
  width: 100%;
  height: 100%;
  background: #dce8e5;
}
.satellite-center-marker {
  width: 18px !important;
  height: 18px !important;
  margin: 0 !important;
  border: 3px solid #0d5e4d;
  border-radius: 50%;
  background: #4fc3a1;
  box-shadow: 0 1px 7px rgba(0, 0, 0, 0.45);
  cursor: grab;
}
.satellite-center-marker.leaflet-marker-dragging { cursor: grabbing; }
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

function shiftedBounds(bounds, latlng) {
  const halfLat = Math.abs(Number(bounds[1][0]) - Number(bounds[0][0])) / 2
  const halfLng = Math.abs(Number(bounds[1][1]) - Number(bounds[0][1])) / 2
  return [
    [latlng.lat - halfLat, latlng.lng - halfLng],
    [latlng.lat + halfLat, latlng.lng + halfLng],
  ]
}

export default async function(component) {
  const { data, parentElement, setStateValue, setTriggerValue } = component
  const L = await ensureLeaflet()
  const shell = parentElement.querySelector('.map-shell')
  const target = parentElement.querySelector('#geo-map')
  const hint = parentElement.querySelector('.map-hint')
  if (!target) return

  const mapHeight = Math.max(120, Number(data.height || 460))
  target.style.height = `${mapHeight}px`
  if (shell) shell.style.height = `${mapHeight}px`

  if (hint) {
    hint.textContent = data.hint || ''
    hint.style.display = data.hint ? 'block' : 'none'
  }

  const selection = {
    lat: Number(data.latitude),
    lng: Number(data.longitude),
  }
  let state = mapInstances.get(parentElement)

  if (!state) {
    const interactive = data.interactive !== false
    const map = L.map(target, {
      zoomControl: interactive,
      dragging: interactive,
      scrollWheelZoom: interactive,
      doubleClickZoom: interactive,
      boxZoom: interactive,
      keyboard: interactive,
      touchZoom: interactive,
      worldCopyJump: true,
    })
      .setView([selection.lat, selection.lng], Number(data.zoom || 5))
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map)
    const markerIcon = L.divIcon({
      className: 'satellite-center-marker',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    })
    const marker = L.marker([selection.lat, selection.lng], {
      icon: markerIcon,
      draggable: interactive,
      keyboard: interactive,
      title: interactive ? 'Drag to move the centre' : 'Selected centre',
    }).addTo(map)
    const rectangle = L.rectangle(data.bounds, {
      color: '#0d5e4d',
      weight: 2,
      fillColor: '#4fc3a1',
      fillOpacity: 0.12,
    }).addTo(map)

    state = {
      map,
      marker,
      rectangle,
      selection,
      interactive,
      dataBounds: data.bounds,
      boundsSignature: JSON.stringify(data.bounds),
    }
    mapInstances.set(parentElement, state)

    if (interactive) {
      const emitPicked = latlng => {
        const picked = {
          lat: Number(latlng.lat.toFixed(6)),
          lng: Number(latlng.lng.toFixed(6)),
          zoom: map.getZoom(),
        }
        state.selection = picked
        marker.setLatLng([picked.lat, picked.lng])
        setStateValue('selection', picked)
        setTriggerValue('picked', picked)
      }
      map.on('click', event => emitPicked(event.latlng))
      marker.on('drag', event => {
        state.rectangle.setBounds(
          shiftedBounds(state.dataBounds, event.target.getLatLng())
        )
      })
      marker.on('dragend', event => emitPicked(event.target.getLatLng()))
    }
    setTimeout(() => {
      map.invalidateSize()
      if (!interactive || data.fit_bounds === true) {
        map.fitBounds(data.bounds, { padding: [18, 18], maxZoom: 11, animate: false })
      }
    }, 0)
  }

  if (changed(state.selection, selection)) {
    state.selection = selection
    state.marker.setLatLng([selection.lat, selection.lng])
    state.map.panTo([selection.lat, selection.lng], { animate: false })
  }
  state.rectangle.setBounds(data.bounds)
  state.dataBounds = data.bounds
  const boundsSignature = JSON.stringify(data.bounds)
  const boundsChanged = state.boundsSignature !== boundsSignature
  state.boundsSignature = boundsSignature
  if (!state.interactive || (data.fit_bounds === true && boundsChanged)) {
    setTimeout(() => {
      state.map.invalidateSize()
      state.map.fitBounds(data.bounds, { padding: [18, 18], maxZoom: 11, animate: false })
    }, 0)
  }
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
    height: int = 460,
    interactive: bool = True,
    fit_bounds: bool = False,
    hint: str = "Click the map or drag the green point to move the area.",
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
            "interactive": interactive,
            "fit_bounds": fit_bounds,
            "hint": hint,
            "height": height,
        },
        default={
            "selection": {"lat": latitude, "lng": longitude, "zoom": zoom}
        },
        on_selection_change=on_selection_change,
        on_picked_change=lambda: None,
        width="stretch",
        height=height,
    )
