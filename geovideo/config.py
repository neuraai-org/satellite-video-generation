from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from geovideo.schemas import InputConfig


@dataclass(frozen=True)
class AppConfig:
    input_config: InputConfig
    seed: Optional[int] = None

    @property
    def cache_dir(self) -> Path:
        return Path(self.input_config.provider.cache_dir)
