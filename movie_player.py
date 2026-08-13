"""Interactive, pauseable satellite time-lapse player using Streamlit CCv2."""

from __future__ import annotations

import base64

import streamlit as st


_PLAYER_HTML = """
<section class="player-shell" aria-label="Satellite time-lapse player">
  <div class="stage">
    <img id="frame" alt="Selected Sentinel-2 acquisition" />
    <div class="topline">
      <span id="date-label"></span>
      <span id="counter"></span>
    </div>
    <div id="cloud-label" class="cloud-label"></div>
  </div>
  <div class="controls">
    <button id="previous" type="button" aria-label="Previous frame">◀</button>
    <button id="play" class="play" type="button" aria-label="Play or pause">▶ Play</button>
    <button id="next" type="button" aria-label="Next frame">▶</button>
    <label class="speed-label" for="speed">Speed</label>
    <select id="speed" aria-label="Playback speed">
      <option value="2000">0.5×</option>
      <option value="1000" selected>1×</option>
      <option value="500">2×</option>
      <option value="250">4×</option>
    </select>
    <label class="loop-label"><input id="loop" type="checkbox" checked /> Loop</label>
  </div>
  <input id="scrubber" class="scrubber" type="range" min="0" value="0" step="1" aria-label="Timeline" />
  <div class="range-labels"><span id="first-date"></span><span id="last-date"></span></div>
</section>
"""

_PLAYER_CSS = """
.player-shell {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto auto auto;
  overflow: hidden;
  color: var(--st-text-color);
  font-family: var(--st-font, sans-serif);
}
* { box-sizing: border-box; }
.stage {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--st-border-color);
  border-radius: var(--st-base-radius, 12px);
  background: var(--st-secondary-background-color, #152125);
}
#frame {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
  background: var(--st-secondary-background-color, #152125);
}
.topline {
  position: absolute;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  left: 12px;
  right: 12px;
  top: 12px;
  pointer-events: none;
}
.topline span, .cloud-label {
  padding: 7px 10px;
  border-radius: 8px;
  background: rgba(5, 16, 18, 0.78);
  color: white;
  font-size: 13px;
  font-weight: 650;
  backdrop-filter: blur(5px);
}
.cloud-label {
  position: absolute;
  right: 12px;
  bottom: 12px;
  pointer-events: none;
}
.controls {
  display: grid;
  grid-template-columns: auto minmax(104px, auto) auto auto auto auto;
  align-items: center;
  gap: 8px;
  margin-top: 9px;
}
button, select {
  min-height: 34px;
  border: 1px solid var(--st-widget-border-color, var(--st-border-color));
  border-radius: var(--st-button-radius, 8px);
  background: var(--st-secondary-background-color);
  color: var(--st-text-color);
  font: inherit;
  cursor: pointer;
}
button { padding: 0 13px; font-weight: 650; }
button:hover, select:hover { border-color: var(--st-primary-color); }
button.play {
  min-width: 104px;
  color: var(--st-background-color);
  background: var(--st-primary-color);
  border-color: var(--st-primary-color);
}
select { padding: 0 10px; }
.speed-label { margin-left: 8px; font-size: 13px; }
.loop-label { display: flex; align-items: center; gap: 5px; font-size: 13px; }
.scrubber {
  width: 100%;
  margin: 9px 0 0;
  accent-color: var(--st-primary-color);
}
.range-labels {
  display: flex;
  justify-content: space-between;
  color: var(--st-gray-text-color, var(--st-text-color));
  font-size: 12px;
}
@media (max-width: 520px) {
  .controls {
    grid-template-columns: auto minmax(96px, 1fr) auto auto auto auto;
    gap: 5px;
  }
  button { padding: 0 8px; }
  .speed-label { display: none; }
}
"""

_PLAYER_JS = """
const players = new WeakMap()

export default function(component) {
  const { data, parentElement } = component
  const frames = Array.isArray(data?.frames) ? data.frames : []
  if (!frames.length) return

  const image = parentElement.querySelector('#frame')
  const dateLabel = parentElement.querySelector('#date-label')
  const cloudLabel = parentElement.querySelector('#cloud-label')
  const counter = parentElement.querySelector('#counter')
  const play = parentElement.querySelector('#play')
  const previous = parentElement.querySelector('#previous')
  const next = parentElement.querySelector('#next')
  const speed = parentElement.querySelector('#speed')
  const loop = parentElement.querySelector('#loop')
  const scrubber = parentElement.querySelector('#scrubber')
  const firstDate = parentElement.querySelector('#first-date')
  const lastDate = parentElement.querySelector('#last-date')

  let state = players.get(parentElement)
  if (!state) {
    state = { index: 0, timer: null, signature: '' }
    players.set(parentElement, state)
  }

  const signature = `${data.movie_id}:${frames.length}`
  if (state.signature !== signature) {
    if (state.timer) clearInterval(state.timer)
    state.timer = null
    state.index = 0
    state.signature = signature
  }

  scrubber.max = String(frames.length - 1)
  firstDate.textContent = frames[0].date_label
  lastDate.textContent = frames[frames.length - 1].date_label

  function render() {
    const frame = frames[state.index]
    image.src = frame.image
    dateLabel.textContent = frame.date_label
    cloudLabel.textContent = `Catalogue cloud: ${Number(frame.cloud_cover).toFixed(1)}%`
    counter.textContent = `${state.index + 1} / ${frames.length}`
    scrubber.value = String(state.index)
  }

  function stop() {
    if (state.timer) clearInterval(state.timer)
    state.timer = null
    play.textContent = '▶ Play'
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
    play.textContent = '❚❚ Pause'
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
    """Render the client-side player without causing Streamlit reruns during playback."""
    return _MOVIE_PLAYER(
        key=key,
        data={"frames": frames, "movie_id": movie_id},
        width="stretch",
        height=500,
    )
