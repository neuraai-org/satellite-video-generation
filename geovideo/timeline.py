from __future__ import annotations

from dataclasses import dataclass
from typing import List

from geovideo.geo import lerp
from geovideo.schemas import TimelineConfig


@dataclass(frozen=True)
class PoiCue:
    index: int
    start: float
    end: float


@dataclass(frozen=True)
class TimelineState:
    active_index: int
    reveal_progress: float
    camera_zoom: float


def ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)


def ease_linear(t: float) -> float:
    return t


def build_poi_cues(count: int, cfg: TimelineConfig) -> List[PoiCue]:
    cues: List[PoiCue] = []
    for idx in range(count):
        start = cfg.intro_delay + idx * cfg.poi_stagger
        cues.append(PoiCue(index=idx, start=start, end=start + cfg.poi_stagger))
    return cues


def camera_zoom_at(t: float, cfg: TimelineConfig, default_zoom: float) -> float:
    start_zoom = cfg.camera_start_zoom or default_zoom
    end_zoom = cfg.camera_end_zoom or default_zoom
    if cfg.duration <= 0:
        return default_zoom
    progress = min(max(t / cfg.duration, 0.0), 1.0)
    ease = ease_in_out if cfg.ease == "ease_in_out" else ease_linear
    return lerp(start_zoom, end_zoom, ease(progress))


def timeline_state_at(t: float, count: int, cfg: TimelineConfig, default_zoom: float) -> TimelineState:
    cues = build_poi_cues(count, cfg)
    active = 0
    reveal = 0.0
    for cue in cues:
        if t >= cue.start:
            active = cue.index
            reveal = min(max((t - cue.start) / max(cfg.poi_stagger, 0.001), 0.0), 1.0)
    zoom = camera_zoom_at(t, cfg, default_zoom)
    return TimelineState(active_index=active, reveal_progress=reveal, camera_zoom=zoom)
