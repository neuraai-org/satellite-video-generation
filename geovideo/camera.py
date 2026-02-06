from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from geovideo.geo import Bounds, bounds_for_points, choose_zoom_for_bounds


@dataclass(frozen=True)
class CameraState:
    center_lat: float
    center_lon: float
    zoom: int


def compute_bounds(center: Tuple[float, float], points: Iterable[Tuple[float, float]]) -> Bounds:
    all_points = [center, *points]
    return bounds_for_points(all_points)


def auto_camera(
    center: Tuple[float, float],
    points: Iterable[Tuple[float, float]],
    width: int,
    height: int,
    margin_ratio: float,
    zoom_override: int | None = None,
) -> CameraState:
    if zoom_override is not None:
        return CameraState(center_lat=center[0], center_lon=center[1], zoom=zoom_override)
    bounds = compute_bounds(center, points)
    zoom = choose_zoom_for_bounds(bounds, width, height, margin_ratio)
    return CameraState(center_lat=center[0], center_lon=center[1], zoom=zoom)
