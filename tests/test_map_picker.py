import inspect

from map_picker import _MAP_JS, location_picker


def test_map_draws_the_selected_bounds():
    assert "L.rectangle(data.bounds" in _MAP_JS
    assert "state.rectangle.setBounds(data.bounds)" in _MAP_JS


def test_green_centre_marker_can_be_dragged_with_its_rectangle():
    assert "draggable: interactive" in _MAP_JS
    assert "marker.on('drag'" in _MAP_JS
    assert "marker.on('dragend'" in _MAP_JS
    assert "shiftedBounds(state.dataBounds" in _MAP_JS


def test_map_supports_compact_read_only_overview():
    parameters = inspect.signature(location_picker).parameters
    assert parameters["height"].default == 460
    assert parameters["interactive"].default is True
    assert parameters["fit_bounds"].default is False
    assert "data.interactive !== false" in _MAP_JS
    assert "target.style.height" in _MAP_JS


def test_map_can_refit_when_the_area_slider_changes():
    assert "data.fit_bounds === true && boundsChanged" in _MAP_JS
    assert "state.boundsSignature !== boundsSignature" in _MAP_JS
