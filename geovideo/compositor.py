from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from geovideo.camera import CameraState
from geovideo.draw import draw_pin, draw_ring, layout_labels, load_font
from geovideo.geo import TILE_SIZE, latlon_to_screen_px, latlon_to_world_px, world_px_to_tile
from geovideo.providers.base import TileProvider
from geovideo.schemas import InputConfig, Poi
from geovideo.timeline import timeline_state_at


@dataclass
class FrameContext:
    time_s: float
    camera: CameraState


class Compositor:
    def __init__(self, config: InputConfig, provider: TileProvider) -> None:
        self.config = config
        self.provider = provider
        self.font = load_font(config.style.font_path, size=32)
        self.small_font = load_font(config.style.font_path, size=24)
        self.overlay: Optional[Image.Image] = None
        if config.style.overlay_path:
            self.overlay = Image.open(config.style.overlay_path).convert("RGBA")

    def render_frame(self, ctx: FrameContext) -> np.ndarray:
        style = self.config.style
        width, height = style.width, style.height
        timeline_state = timeline_state_at(
            ctx.time_s, len(self.config.pois), self.config.timeline, ctx.camera.zoom
        )
        camera = CameraState(
            center_lat=ctx.camera.center_lat,
            center_lon=ctx.camera.center_lon,
            zoom=int(round(timeline_state.camera_zoom)),
        )
        base = self._render_basemap(camera, width, height).convert("RGBA")
        draw = ImageDraw.Draw(base)
        self._draw_polygon(draw, camera)
        self._draw_connectors(draw, camera)
        self._draw_pois(draw, camera, timeline_state.active_index)
        self._draw_rings(draw, camera, timeline_state)
        self._draw_labels(draw, camera)
        self._draw_subtitle(draw, width, height)
        self._draw_overlay(base, width, height)
        self._draw_attribution(draw, width, height)
        array = np.array(base.convert("RGB"))
        return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)

    def _render_basemap(self, camera: CameraState, width: int, height: int) -> Image.Image:
        center_x, center_y = latlon_to_world_px(camera.center_lat, camera.center_lon, camera.zoom)
        top_left_x = center_x - width / 2
        top_left_y = center_y - height / 2
        start_tile_x, start_tile_y = world_px_to_tile(top_left_x, top_left_y)
        end_tile_x, end_tile_y = world_px_to_tile(top_left_x + width, top_left_y + height)

        canvas = Image.new("RGB", (width, height))
        for tile_x in range(start_tile_x, end_tile_x + 1):
            for tile_y in range(start_tile_y, end_tile_y + 1):
                tile = self.provider.get_tile(camera.zoom, tile_x, tile_y)
                px = int(tile_x * TILE_SIZE - top_left_x)
                py = int(tile_y * TILE_SIZE - top_left_y)
                canvas.paste(tile, (px, py))
        return canvas

    def _draw_polygon(self, draw: ImageDraw.ImageDraw, camera: CameraState) -> None:
        style = self.config.style
        if not style.show_polygon or not style.polygon_points:
            return
        points: List[Tuple[float, float]] = []
        for location in style.polygon_points:
            x, y = latlon_to_screen_px(
                location.lat,
                location.lon,
                camera.zoom,
                camera.center_lat,
                camera.center_lon,
                style.width,
                style.height,
            )
            points.append((x, y))
        if len(points) < 3:
            return
        draw.polygon(points, fill=(0, 128, 255, 70), outline=(0, 128, 255))

    def _draw_connectors(self, draw: ImageDraw.ImageDraw, camera: CameraState) -> None:
        if not self.config.style.show_connectors:
            return
        center = self.config.center
        for poi in self.config.pois:
            x1, y1 = latlon_to_screen_px(
                center.lat,
                center.lon,
                camera.zoom,
                camera.center_lat,
                camera.center_lon,
                self.config.style.width,
                self.config.style.height,
            )
            x2, y2 = latlon_to_screen_px(
                poi.lat,
                poi.lon,
                camera.zoom,
                camera.center_lat,
                camera.center_lon,
                self.config.style.width,
                self.config.style.height,
            )
            draw.line((x1, y1, x2, y2), fill=(255, 255, 255, 120), width=2)

    def _draw_pois(self, draw: ImageDraw.ImageDraw, camera: CameraState, active_index: int) -> None:
        for idx, poi in enumerate(self.config.pois):
            x, y = latlon_to_screen_px(
                poi.lat,
                poi.lon,
                camera.zoom,
                camera.center_lat,
                camera.center_lon,
                self.config.style.width,
                self.config.style.height,
            )
            color = _poi_color(poi)
            if idx == active_index:
                color = tuple(min(c + 40, 255) for c in color)
            draw_pin(draw, int(x), int(y), color)

    def _draw_rings(self, draw: ImageDraw.ImageDraw, camera: CameraState, timeline_state) -> None:
        if not self.config.pois:
            return
        idx = min(timeline_state.active_index, len(self.config.pois) - 1)
        poi = self.config.pois[idx]
        x, y = latlon_to_screen_px(
            poi.lat,
            poi.lon,
            camera.zoom,
            camera.center_lat,
            camera.center_lon,
            self.config.style.width,
            self.config.style.height,
        )
        period = max(self.config.timeline.ring_period, 0.1)
        phase = (timeline_state.reveal_progress + (timeline_state.active_index * 0.3)) % 1.0
        radius = int(24 + phase * 40)
        alpha = int(200 * (1 - phase))
        draw_ring(draw, int(x), int(y), radius, alpha)

    def _draw_labels(self, draw: ImageDraw.ImageDraw, camera: CameraState) -> None:
        labels = []
        for poi in self.config.pois:
            x, y = latlon_to_screen_px(
                poi.lat,
                poi.lon,
                camera.zoom,
                camera.center_lat,
                camera.center_lon,
                self.config.style.width,
                self.config.style.height,
            )
            labels.append((poi.name, (int(x), int(y))))
        placements = layout_labels(self._dummy_canvas(), labels, self.small_font)
        for placement in placements:
            draw.rounded_rectangle(placement.box, radius=8, fill=(0, 0, 0, 180))
            draw.text(placement.position, placement.text, font=self.small_font, fill=(255, 255, 255))

    def _draw_subtitle(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        if not self.config.style.subtitle:
            return
        text = self.config.style.subtitle
        text_w, text_h = self.font.getbbox(text)[2:4]
        x = (width - text_w) // 2
        y = height - text_h - self.config.style.safe_margin_px
        draw.rounded_rectangle(
            (x - 20, y - 12, x + text_w + 20, y + text_h + 12),
            radius=12,
            fill=(0, 0, 0, 160),
        )
        draw.text((x, y), text, font=self.font, fill=(255, 255, 255))

    def _draw_overlay(self, base: Image.Image, width: int, height: int) -> None:
        if not self.overlay:
            return
        overlay = self.overlay
        ratio = min(width / overlay.width, height / overlay.height)
        scaled = overlay.resize((int(overlay.width * ratio), int(overlay.height * ratio)))
        x = width - scaled.width - 20
        y = int(height * 0.2)
        base.alpha_composite(scaled, (x, y))

    def _draw_attribution(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        text = self.config.style.watermark_text or self.provider.attribution
        text_w, text_h = self.small_font.getbbox(text)[2:4]
        x = width - text_w - 12
        y = height - text_h - 12
        draw.text((x, y), text, font=self.small_font, fill=(255, 255, 255))

    def _dummy_canvas(self) -> Image.Image:
        return Image.new("RGB", (self.config.style.width, self.config.style.height))


def _poi_color(poi: Poi) -> Tuple[int, int, int]:
    colors = {
        "school": (255, 196, 0),
        "market": (0, 200, 120),
        "food": (255, 90, 90),
        "other": (80, 160, 255),
    }
    return colors.get(poi.type, (200, 200, 200))
