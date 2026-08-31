"""Zoomable, pauseable satellite time-lapse player using Streamlit CCv2."""

from __future__ import annotations

import base64

import streamlit as st


_PLAYER_HTML = """
<section class="player-shell" aria-label="Satellite time-lapse player">
  <header class="frame-info">
    <div>
      <div class="info-label">Acquisition date</div>
      <div id="date-label" class="date-label"></div>
    </div>
    <div class="frame-details">
      <span id="counter"></span>
      <span id="cloud-label"></span>
    </div>
  </header>

  <div class="stage" tabindex="0" aria-label="Zoomable satellite image">
    <img id="frame" alt="Selected Sentinel-2 acquisition" draggable="false" />
  </div>

  <div class="control-panel">
    <div class="toolbar">
      <div id="transport" class="control-group transport">
        <button id="previous" type="button" aria-label="Previous frame">Previous</button>
        <button id="play" class="play" type="button" aria-label="Play or pause">Play</button>
        <button id="next" type="button" aria-label="Next frame">Next</button>
        <label for="speed">Speed</label>
        <select id="speed" aria-label="Playback speed">
          <option value="2000">0.5×</option>
          <option value="1000" selected>1×</option>
          <option value="500">2×</option>
          <option value="250">4×</option>
        </select>
        <label class="loop-label"><input id="loop" type="checkbox" checked /> Loop</label>
      </div>
      <div class="control-group zoom-controls">
        <button id="zoom-out" type="button" aria-label="Zoom out">−</button>
        <span id="zoom-label" aria-live="polite">100%</span>
        <button id="zoom-in" type="button" aria-label="Zoom in">+</button>
        <button id="fit" type="button">Fit image</button>
        <button id="fullscreen" type="button">Full screen</button>
      </div>
    </div>
    <div id="timeline" class="timeline">
      <input id="scrubber" type="range" min="0" value="0" step="1" aria-label="Timeline" />
      <div class="range-labels"><span id="first-date"></span><span id="last-date"></span></div>
    </div>
    <div class="interaction-help">Mouse wheel or +/− to zoom up to 16× · drag the image to move · double-click to reset</div>
  </div>
</section>
"""

_PLAYER_CSS = """
* { box-sizing: border-box; }
.player-shell {
  width: 100%;
  display: grid;
  gap: 10px;
  color: var(--st-text-color);
  font-family: var(--st-font, sans-serif);
}
.frame-info {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  min-height: 52px;
  padding: 0 2px;
}
.info-label {
  color: var(--st-gray-text-color, var(--st-text-color));
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.date-label {
  margin-top: 2px;
  font-size: clamp(18px, 2vw, 26px);
  font-weight: 720;
  line-height: 1.15;
}
.frame-details {
  display: flex;
  flex-wrap: wrap;
  justify-content: end;
  gap: 7px;
}
.frame-details span {
  padding: 6px 9px;
  border: 1px solid var(--st-border-color);
  border-radius: var(--st-base-radius, 8px);
  background: var(--st-secondary-background-color);
  font-size: 12px;
  font-weight: 650;
}
.stage {
  position: relative;
  width: 100%;
  height: clamp(320px, calc(100vh - 350px), 720px);
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--st-border-color);
  border-radius: var(--st-base-radius, 12px);
  background: #071012;
  cursor: grab;
  touch-action: none;
  user-select: none;
}
.stage.dragging { cursor: grabbing; }
#frame {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
  background: #071012;
  transform-origin: center center;
  will-change: transform;
  pointer-events: none;
}
.control-panel {
  padding: 10px 12px 9px;
  border: 1px solid var(--st-border-color);
  border-radius: var(--st-base-radius, 12px);
  background: var(--st-secondary-background-color);
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 9px;
}
.control-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
}
button, select {
  min-height: 35px;
  border: 1px solid var(--st-widget-border-color, var(--st-border-color));
  border-radius: var(--st-button-radius, 8px);
  background: var(--st-background-color);
  color: var(--st-text-color);
  font: inherit;
  cursor: pointer;
}
button { padding: 0 12px; font-weight: 650; }
button:hover, select:hover { border-color: var(--st-primary-color); }
button.play {
  min-width: 76px;
  color: var(--st-background-color);
  background: var(--st-primary-color);
  border-color: var(--st-primary-color);
}
select { padding: 0 9px; }
.control-group label, .loop-label { font-size: 13px; }
.loop-label { display: flex; align-items: center; gap: 5px; }
#zoom-label { min-width: 48px; text-align: center; font-size: 13px; font-weight: 700; }
.timeline { margin-top: 9px; }
#scrubber { width: 100%; margin: 0; accent-color: var(--st-primary-color); }
.range-labels {
  display: flex;
  justify-content: space-between;
  color: var(--st-gray-text-color, var(--st-text-color));
  font-size: 12px;
}
.interaction-help {
  margin-top: 6px;
  color: var(--st-gray-text-color, var(--st-text-color));
  font-size: 12px;
}
[hidden] { display: none !important; }
.player-shell:fullscreen {
  height: 100vh;
  padding: 14px;
  grid-template-rows: auto minmax(0, 1fr) auto;
  background: var(--st-background-color, #0b1517);
}
.player-shell:fullscreen .stage { height: auto; }
@media (max-width: 720px) {
  .stage { height: clamp(280px, 52vh, 520px); }
  .frame-info { align-items: start; flex-direction: column; gap: 7px; }
  .frame-details { justify-content: start; }
  .toolbar { align-items: stretch; flex-direction: column; }
  .control-group { width: 100%; }
  .zoom-controls button { flex: 1; }
}
"""

_PLAYER_JS = """
const players = new WeakMap()

export default function(component) {
  const { data, parentElement } = component
  const frames = Array.isArray(data?.frames) ? data.frames : []
  if (!frames.length) return

  const shell = parentElement.querySelector('.player-shell')
  const stage = parentElement.querySelector('.stage')
  const image = parentElement.querySelector('#frame')
  const dateLabel = parentElement.querySelector('#date-label')
  const cloudLabel = parentElement.querySelector('#cloud-label')
  const counter = parentElement.querySelector('#counter')
  const play = parentElement.querySelector('#play')
  const previous = parentElement.querySelector('#previous')
  const next = parentElement.querySelector('#next')
  const speed = parentElement.querySelector('#speed')
  const loop = parentElement.querySelector('#loop')
  const transport = parentElement.querySelector('#transport')
  const timeline = parentElement.querySelector('#timeline')
  const scrubber = parentElement.querySelector('#scrubber')
  const firstDate = parentElement.querySelector('#first-date')
  const lastDate = parentElement.querySelector('#last-date')
  const zoomOut = parentElement.querySelector('#zoom-out')
  const zoomIn = parentElement.querySelector('#zoom-in')
  const zoomLabel = parentElement.querySelector('#zoom-label')
  const fit = parentElement.querySelector('#fit')
  const fullscreen = parentElement.querySelector('#fullscreen')

  let state = players.get(parentElement)
  if (!state) {
    state = {
      index: 0,
      timer: null,
      signature: '',
      scale: 1,
      x: 0,
      y: 0,
      dragging: false,
      pointerX: 0,
      pointerY: 0,
    }
    players.set(parentElement, state)
  }

  const signature = `${data.movie_id}:${frames.length}`
  if (state.signature !== signature) {
    if (state.timer) clearInterval(state.timer)
    Object.assign(state, { timer: null, index: 0, scale: 1, x: 0, y: 0 })
    state.signature = signature
  }

  const hasTimeline = frames.length > 1
  transport.hidden = !hasTimeline
  timeline.hidden = !hasTimeline
  scrubber.max = String(frames.length - 1)
  firstDate.textContent = frames[0].date_label
  lastDate.textContent = frames[frames.length - 1].date_label

  function clampPan() {
    if (state.scale <= 1) {
      state.x = 0
      state.y = 0
      return
    }
    const maxX = stage.clientWidth * (state.scale - 1) / 2
    const maxY = stage.clientHeight * (state.scale - 1) / 2
    state.x = Math.max(-maxX, Math.min(maxX, state.x))
    state.y = Math.max(-maxY, Math.min(maxY, state.y))
  }

  function applyTransform() {
    clampPan()
    image.style.transform = `translate(${state.x}px, ${state.y}px) scale(${state.scale})`
    zoomLabel.textContent = `${Math.round(state.scale * 100)}%`
  }

  function setZoom(nextScale, focusX = 0, focusY = 0) {
    const bounded = Math.max(1, Math.min(16, nextScale))
    const ratio = bounded / state.scale
    state.x = focusX * (1 - ratio) + state.x * ratio
    state.y = focusY * (1 - ratio) + state.y * ratio
    state.scale = bounded
    applyTransform()
  }

  function resetView() {
    Object.assign(state, { scale: 1, x: 0, y: 0 })
    applyTransform()
  }

  function render() {
    const frame = frames[state.index]
    image.src = frame.image
    dateLabel.textContent = frame.date_label
    cloudLabel.textContent = `Catalogue cloud ${Number(frame.cloud_cover).toFixed(1)}%`
    counter.textContent = hasTimeline ? `Frame ${state.index + 1} of ${frames.length}` : 'Single image'
    scrubber.value = String(state.index)
    applyTransform()
  }

  function stop() {
    if (state.timer) clearInterval(state.timer)
    state.timer = null
    play.textContent = 'Play'
  }

  function step(direction = 1) {
    const candidate = state.index + direction
    if (candidate >= frames.length) {
      if (loop.checked) state.index = 0
      else { state.index = frames.length - 1; stop() }
    } else if (candidate < 0) {
      state.index = loop.checked ? frames.length - 1 : 0
    } else {
      state.index = candidate
    }
    render()
  }

  function start() {
    stop()
    play.textContent = 'Pause'
    state.timer = setInterval(() => step(1), Number(speed.value))
  }

  play.onclick = () => state.timer ? stop() : start()
  previous.onclick = () => { stop(); step(-1) }
  next.onclick = () => { stop(); step(1) }
  speed.onchange = () => { if (state.timer) start() }
  scrubber.oninput = event => {
    stop()
    state.index = Number(event.target.value)
    render()
  }
  zoomIn.onclick = () => setZoom(state.scale * 1.35)
  zoomOut.onclick = () => setZoom(state.scale / 1.35)
  fit.onclick = resetView
  stage.ondblclick = resetView
  stage.onwheel = event => {
    event.preventDefault()
    const rect = stage.getBoundingClientRect()
    const focusX = event.clientX - rect.left - rect.width / 2
    const focusY = event.clientY - rect.top - rect.height / 2
    setZoom(state.scale * (event.deltaY < 0 ? 1.18 : 1 / 1.18), focusX, focusY)
  }
  stage.onpointerdown = event => {
    if (state.scale <= 1) return
    state.dragging = true
    state.pointerX = event.clientX
    state.pointerY = event.clientY
    stage.classList.add('dragging')
    stage.setPointerCapture(event.pointerId)
  }
  stage.onpointermove = event => {
    if (!state.dragging) return
    state.x += event.clientX - state.pointerX
    state.y += event.clientY - state.pointerY
    state.pointerX = event.clientX
    state.pointerY = event.clientY
    applyTransform()
  }
  stage.onpointerup = event => {
    state.dragging = false
    stage.classList.remove('dragging')
    if (stage.hasPointerCapture(event.pointerId)) stage.releasePointerCapture(event.pointerId)
  }
  stage.onpointercancel = stage.onpointerup
  fullscreen.onclick = async () => {
    if (document.fullscreenElement) await document.exitFullscreen()
    else if (shell.requestFullscreen) await shell.requestFullscreen()
  }
  shell.onfullscreenchange = () => {
    fullscreen.textContent = document.fullscreenElement ? 'Exit full screen' : 'Full screen'
    setTimeout(applyTransform, 0)
  }

  render()

  return () => {
    if (state.timer) clearInterval(state.timer)
    players.delete(parentElement)
  }
}
"""


_MOVIE_PLAYER = st.components.v2.component(
    "sentinel_delta_movie_player",
    html=_PLAYER_HTML,
    css=_PLAYER_CSS,
    js=_PLAYER_JS,
)


def encode_frame(image: bytes, date_label: str, cloud_cover: float) -> dict:
    """Return a serializable browser payload for one JPEG frame."""
    encoded = base64.b64encode(image).decode("ascii")
    return {
        "image": f"data:image/jpeg;base64,{encoded}",
        "date_label": date_label,
        "cloud_cover": float(cloud_cover),
    }


def satellite_movie(frames: list[dict], *, movie_id: str, key: str):
    """Render a responsive client-side player with pan, zoom and playback."""
    return _MOVIE_PLAYER(
        key=key,
        data={"frames": frames, "movie_id": movie_id},
        width="stretch",
        height="content",
    )
