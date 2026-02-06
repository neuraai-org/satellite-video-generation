from geovideo.geo import bounds_for_points, choose_zoom_for_bounds, latlon_to_world_px


def test_latlon_to_world_px_origin():
    x, y = latlon_to_world_px(0.0, 0.0, zoom=1)
    assert x > 0
    assert y > 0


def test_bounds_and_zoom():
    bounds = bounds_for_points([(0.0, 0.0), (10.0, 10.0)])
    zoom = choose_zoom_for_bounds(bounds, width=1080, height=1920, margin_ratio=0.1)
    assert zoom >= 1
