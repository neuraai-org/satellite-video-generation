from __future__ import annotations

from pathlib import Path

from geovideo.providers.base import TileProvider


def build_osm_provider(cache_dir: str, max_retries: int, throttle_s: float) -> TileProvider:
    return TileProvider(
        name="osm",
        url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution="© OpenStreetMap contributors",
        cache_dir=Path(cache_dir),
        max_retries=max_retries,
        throttle_s=throttle_s,
    )
