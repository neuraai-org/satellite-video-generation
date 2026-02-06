from __future__ import annotations

from pathlib import Path

from geovideo.providers.base import TileProvider


def build_mapbox_provider(cache_dir: str, api_key: str, max_retries: int, throttle_s: float) -> TileProvider:
    return TileProvider(
        name="mapbox",
        url_template=(
            "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/tiles/256/{z}/{x}/{y}?access_token={api_key}"
        ),
        attribution="© Mapbox © OpenStreetMap",
        api_key=api_key,
        cache_dir=Path(cache_dir),
        max_retries=max_retries,
        throttle_s=throttle_s,
    )
