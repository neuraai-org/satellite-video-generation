from __future__ import annotations

import io
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from PIL import Image


@dataclass
class TileProvider:
    name: str
    url_template: str
    attribution: str
    api_key: Optional[str] = None
    cache_dir: Path = Path(".cache/tiles")
    max_retries: int = 3
    throttle_s: float = 0.1

    def _cache_path(self, z: int, x: int, y: int) -> Path:
        return self.cache_dir / self.name / str(z) / str(x) / f"{y}.png"

    def _throttle(self) -> None:
        if self.throttle_s > 0:
            time.sleep(self.throttle_s)

    def get_tile(self, z: int, x: int, y: int) -> Image.Image:
        path = self._cache_path(z, x, y)
        if path.exists():
            return Image.open(path).convert("RGB")
        url = self.url_template.format(z=z, x=x, y=y, api_key=self.api_key or "")
        path.parent.mkdir(parents=True, exist_ok=True)
        last_error: Optional[Exception] = None
        for _ in range(self.max_retries):
            try:
                self._throttle()
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content)).convert("RGB")
                image.save(path)
                return image
            except Exception as exc:  # noqa: BLE001 - propagate after retries
                last_error = exc
        raise RuntimeError(f"Failed to fetch tile {z}/{x}/{y}: {last_error}")
