from __future__ import annotations

from pathlib import Path

from geovideo.providers.base import TileProvider
from geovideo.providers.mapbox import build_mapbox_provider
from geovideo.providers.osm import build_osm_provider
from geovideo.schemas import ProviderConfig


def build_provider(config: ProviderConfig) -> TileProvider:
    if config.name == "osm":
        return build_osm_provider(config.cache_dir, config.max_retries, config.throttle_s)
    if config.name == "mapbox":
        if not config.api_key:
            raise ValueError("Mapbox api_key is required")
        return build_mapbox_provider(config.cache_dir, config.api_key, config.max_retries, config.throttle_s)
    if config.name == "custom":
        return TileProvider(
            name="custom",
            url_template=config.url_template or "",
            attribution="© Custom tiles",
            api_key=config.api_key,
            cache_dir=Path(config.cache_dir),
            max_retries=config.max_retries,
            throttle_s=config.throttle_s,
        )
    raise ValueError(f"Unknown provider {config.name}")
