from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Location(BaseModel):
    name: str = Field(..., min_length=1)
    lat: float
    lon: float

    @field_validator("lat")
    @classmethod
    def _lat_range(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("lat must be in [-90, 90]")
        return value

    @field_validator("lon")
    @classmethod
    def _lon_range(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("lon must be in [-180, 180]")
        return value


PoiType = Literal["school", "market", "food", "other"]


class Poi(Location):
    type: PoiType = "other"


class StyleConfig(BaseModel):
    width: int = 1080
    height: int = 1920
    fps: int = 30
    margin_ratio: float = 0.12
    font_path: Optional[str] = None
    subtitle: Optional[str] = None
    show_connectors: bool = True
    show_polygon: bool = False
    polygon_points: Optional[list[Location]] = None
    overlay_path: Optional[str] = None
    watermark_text: str = "© OpenStreetMap contributors"
    safe_margin_px: int = 80


class TimelineConfig(BaseModel):
    duration: float = 10.0
    intro_delay: float = 0.5
    poi_stagger: float = 0.8
    ring_period: float = 1.6
    ease: Literal["linear", "ease_in_out"] = "ease_in_out"
    camera_start_zoom: Optional[int] = None
    camera_end_zoom: Optional[int] = None


class OutputConfig(BaseModel):
    path: str = "output.mp4"
    crf: int = 18
    bitrate: Optional[str] = None
    preset: str = "medium"
    faststart: bool = True


class AudioConfig(BaseModel):
    music_path: Optional[str] = None
    voiceover_path: Optional[str] = None
    music_volume: float = 0.5
    voiceover_volume: float = 1.0
    ducking_ratio: float = 0.35
    fade_in: float = 0.4
    fade_out: float = 0.6


class ProviderConfig(BaseModel):
    name: Literal["osm", "mapbox", "custom"] = "osm"
    api_key: Optional[str] = None
    url_template: Optional[str] = None
    cache_dir: str = ".cache/tiles"
    max_retries: int = 3
    throttle_s: float = 0.1

    @model_validator(mode="after")
    def _validate_provider(self) -> "ProviderConfig":
        if self.name == "mapbox" and not self.api_key:
            raise ValueError("mapbox provider requires api_key")
        if self.name == "custom" and not self.url_template:
            raise ValueError("custom provider requires url_template")
        return self


class InputConfig(BaseModel):
    center: Location
    pois: list[Poi] = Field(default_factory=list)
    style: StyleConfig = Field(default_factory=StyleConfig)
    timeline: TimelineConfig = Field(default_factory=TimelineConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    max_pois: int = 30

    @model_validator(mode="after")
    def _validate_pois(self) -> "InputConfig":
        if len(self.pois) > self.max_pois:
            raise ValueError("Too many POIs")
        return self
