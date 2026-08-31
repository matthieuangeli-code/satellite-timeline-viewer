from movie_player import _PLAYER_CSS, _PLAYER_HTML, _PLAYER_JS, encode_frame


def test_encode_frame_creates_browser_safe_data_url():
    frame = encode_frame(b"jpeg-bytes", "01 Jan 2026", 12.5)
    assert frame["image"].startswith("data:image/jpeg;base64,")
    assert frame["date_label"] == "01 Jan 2026"
    assert frame["cloud_cover"] == 12.5


def test_date_and_controls_are_outside_the_image_stage():
    stage = _PLAYER_HTML.split('<div class="stage"', 1)[1].split("</div>", 1)[0]
    assert "date-label" not in stage
    assert "control-panel" not in stage


def test_player_supports_pan_zoom_fit_and_responsive_height():
    assert "calc(100vh - 350px)" in _PLAYER_CSS
    assert "stage.onwheel" in _PLAYER_JS
    assert "stage.onpointermove" in _PLAYER_JS
    assert "function resetView()" in _PLAYER_JS
    assert "requestFullscreen" in _PLAYER_JS
    assert "Math.min(16, nextScale)" in _PLAYER_JS
