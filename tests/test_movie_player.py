from movie_player import encode_frame


def test_encode_frame_creates_browser_safe_data_url():
    frame = encode_frame(b"jpeg-bytes", "01 Jan 2026", 12.5)
    assert frame["image"].startswith("data:image/jpeg;base64,")
    assert frame["date_label"] == "01 Jan 2026"
    assert frame["cloud_cover"] == 12.5

