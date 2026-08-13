# Satellite Timeline

A personal Streamlit app for exploring public Sentinel-2 imagery in two modes.

## Delta movie

Choose one of ten curated river deltas and build a chronological satellite time-lapse:

- Mississippi, Nile, Mekong and Ganges–Brahmaputra;
- Danube, Rhône and Niger inland delta;
- Amazon, Lena and Okavango inland delta.

The player includes every successfully readable acquisition matching the chosen period and catalogue-cloud threshold. It provides:

- play and pause;
- previous and next frame;
- draggable time scrubber;
- 0.5×, 1×, 2× and 4× playback speed;
- optional looping;
- the real date, UTC time and catalogue cloud value on every frame.

The Delta view is designed as a single-screen workspace: the full movie and playback controls remain together on the left without an internal scrollbar, while a compact world map and build settings stay visible on the right. The catalogue contains 30 deltas, grouped into river-, wave- and tide-dominated examples.

Before any catalogue search or image download, the app asks for explicit confirmation of the exact centre, width and WGS84 bounding box. Blank, black or partially uncovered crops are rejected automatically and never enter the movie.

Available time spans are 6 months, 1 year, 2 years, 5 years, 10 years, or the complete Sentinel-2 Collection 1 L2A archive from 27 June 2015 to today. Catalogue pagination is followed automatically, so long searches are not silently truncated at 200 acquisitions.

The three labels are simplified dominant-process categories for visual exploration, following the river–wave–tide framework. Real deltas occupy a continuum and their dominant forcing can vary through time and across the delta. See [Broaddus et al. (2022)](https://doi.org/10.1029/2022GL100355) and [Vulis et al. (2023)](https://doi.org/10.1029/2022GL102684) for quantitative treatments of this framework.

The movie uses the small georeferenced Sentinel-2 preview for fast loading. It is intended to reveal large changes in water, sediment, vegetation, ice and coastline—not fine details. Frames are observations, not interpolated animation.

## Anywhere on Earth

Click anywhere on the world map, choose an area and browse the available acquisitions one at a time with the timeline slider.

## Run locally

```powershell
cd C:\Users\matth\Business\satellite-timeline-viewer
.\.venv\Scripts\streamlit.exe run streamlit_app.py --server.port 8502
```

Open <http://localhost:8502>.

For a fresh installation:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

No API key is required. The app uses the public Earth Search catalogue and Sentinel-2 COG/preview assets on AWS Open Data.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Interpretation limits

- Catalogue cloud cover applies to the complete Sentinel tile, not just the displayed crop.
- Tides, seasons, cloud, haze, snow and sun angle can look like geographic movement.
- Sentinel-2 natural colour is suitable for large-scale change, not precise shoreline surveying.
- The movie omits a catalogue acquisition if its preview cannot be downloaded or read.
- The two-year option can contain many frames and take longer on the first build; later identical builds use the Streamlit cache.
