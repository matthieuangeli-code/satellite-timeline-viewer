import inspect

from map_picker import _MAP_JS, area_preview, location_picker


def test_map_draws_the_selected_bounds():
    assert "L.rectangle(data.bounds" in _MAP_JS
    assert "state.rectangle.setBounds(data.bounds)" in _MAP_JS


def test_map_supports_compact_read_only_overview():
    parameters = inspect.signature(location_picker).parameters
    assert parameters["height"].default == 460
    assert parameters["interactive"].default is True
    assert "data.interactive !== false" in _MAP_JS
    assert "target.style.height" in _MAP_JS


def test_dialog_area_preview_uses_native_polygon_map():
    source = inspect.getsource(area_preview)
    assert '"PolygonLayer"' in source
    assert "st.pydeck_chart" in source
