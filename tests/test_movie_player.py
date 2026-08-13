from movie_player import _PLAYER_CSS, encode_frame


def test_encode_frame_creates_browser_safe_data_url():
    frame = encode_frame(b"jpeg-bytes", "01 Jan 2026", 12.5)
    assert frame["image"].startswith("data:image/jpeg;base64,")
    assert frame["date_label"] == "01 Jan 2026"
    assert frame["cloud_cover"] == 12.5


def test_player_uses_fixed_grid_without_internal_scroll():
    assert "grid-template-rows: minmax(0, 1fr) auto auto auto;" in _PLAYER_CSS
    assert _PLAYER_CSS.count("overflow: hidden;") >= 2
