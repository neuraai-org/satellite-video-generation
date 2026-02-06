from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Tuple

TILE_SIZE = 256


@dataclass(frozen=True)
class Bounds:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def padded(self, pad_lat: float, pad_lon: float) -> "Bounds":
        return Bounds(
            self.min_lat - pad_lat,
            self.min_lon - pad_lon,
            self.max_lat + pad_lat,
            self.max_lon + pad_lon,
        )


def clamp_lat(lat: float) -> float:
    return max(min(lat, 85.05112878), -85.05112878)


def latlon_to_world_px(lat: float, lon: float, zoom: int) -> Tuple[float, float]:
    lat = clamp_lat(lat)
    scale = TILE_SIZE * (2**zoom)
    x = (lon + 180.0) / 360.0 * scale
    sin_lat = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale
    return x, y


def world_px_to_tile(x: float, y: float) -> Tuple[int, int]:
    return int(x // TILE_SIZE), int(y // TILE_SIZE)


def latlon_to_screen_px(
    lat: float,
    lon: float,
    zoom: int,
    center_lat: float,
    center_lon: float,
    width: int,
    height: int,
) -> Tuple[float, float]:
    center_x, center_y = latlon_to_world_px(center_lat, center_lon, zoom)
    px, py = latlon_to_world_px(lat, lon, zoom)
    return (px - center_x + width / 2, py - center_y + height / 2)


def bounds_for_points(points: Iterable[Tuple[float, float]]) -> Bounds:
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return Bounds(min(lats), min(lons), max(lats), max(lons))


def choose_zoom_for_bounds(
    bounds: Bounds, width: int, height: int, margin_ratio: float
) -> int:
    usable_w = width * (1 - margin_ratio * 2)
    usable_h = height * (1 - margin_ratio * 2)
    for zoom in range(20, 0, -1):
        min_x, min_y = latlon_to_world_px(bounds.min_lat, bounds.min_lon, zoom)
        max_x, max_y = latlon_to_world_px(bounds.max_lat, bounds.max_lon, zoom)
        if max_x - min_x <= usable_w and max_y - min_y <= usable_h:
            return zoom
    return 1


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
