from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

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
        self.large_font = load_font(config.style.font_path, size=44)
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
        if style.ui_preset == "social_map" and style.social_zoom_factor > 1.0:
            base = self._apply_social_zoom(base, style.social_zoom_factor)
        if style.ui_preset == "social_map":
            self._draw_map_tint(base, width, height)
        draw = ImageDraw.Draw(base)
        self._draw_polygon(draw, camera)
        if style.ui_preset == "classic":
            self._draw_connectors(draw, camera)
        self._draw_pois(draw, camera, timeline_state.active_index)
        self._draw_rings(draw, camera, timeline_state)
        self._draw_labels(draw, camera)
        self._draw_center_marker(draw, camera)
        if style.ui_preset == "classic":
            self._draw_subtitle(draw, width, height)
        if style.ui_preset == "social_map" and style.show_social_chrome:
            # In social_map preset, prioritize social chrome over the overlay to avoid visual conflicts.
            self._draw_social_chrome(draw, width, height)
        else:
            self._draw_overlay(base, width, height)
        self._draw_attribution(draw, width, height)
        array = np.array(base.convert("RGB"))
        return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)

    def _apply_social_zoom(self, base: Image.Image, factor: float) -> Image.Image:
        factor = min(max(factor, 1.0), 2.0)
        width, height = base.size
        crop_w = int(width / factor)
        crop_h = int(height / factor)
        left = (width - crop_w) // 2
        top = (height - crop_h) // 2
        cropped = base.crop((left, top, left + crop_w, top + crop_h))
        return cropped.resize((width, height), resample=Image.Resampling.LANCZOS)

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
        if style.ui_preset == "social_map":
            draw.polygon(points, outline=(245, 219, 72, 220), width=4)
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
            if self.config.style.ui_preset == "social_map":
                draw_pin(draw, int(x), int(y), (225, 35, 44))
                draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(255, 255, 255))
            else:
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
        phase = (timeline_state.reveal_progress + (timeline_state.active_index * 0.3)) % 1.0
        if self.config.style.ui_preset == "social_map":
            radius = int(28 + phase * 36)
            alpha = int(190 * (1 - phase))
        else:
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
            if self.config.style.ui_preset == "social_map":
                label_text = placement.text.upper()
                text_w, text_h = self.small_font.getbbox(label_text)[2:4]
                x1 = placement.position[0] - 10
                y1 = placement.position[1] - 4
                x2 = x1 + text_w + 20
                y2 = y1 + text_h + 8
                draw.rectangle((x1, y1, x2, y2), fill=(180, 0, 8, 230))
                draw.text((x1 + 10, y1 + 4), label_text, font=self.small_font, fill=(255, 255, 255))
            else:
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
        if self.config.style.ui_preset == "social_map":
            x = 24
            y = height - text_h - 220
            draw.text((x, y), text, font=self.small_font, fill=(255, 255, 255, 210))
        else:
            x = width - text_w - 12
            y = height - text_h - 12
            draw.text((x, y), text, font=self.small_font, fill=(255, 255, 255))

    def _draw_map_tint(self, base: Image.Image, width: int, height: int) -> None:
        base_rgb = base.convert("RGB")
        base_rgb = ImageEnhance.Color(base_rgb).enhance(0.52)
        base_rgb = ImageEnhance.Contrast(base_rgb).enhance(1.16)
        base_rgb = ImageEnhance.Brightness(base_rgb).enhance(0.84)
        base.paste(base_rgb.convert("RGBA"))

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 35))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle((0, 0, width, height), fill=(10, 38, 28, 22))

        # Create top gradient using vectorized numpy operations instead of per-line drawing
        top_gradient_h = int(height * 0.22)
        if top_gradient_h > 0:
            # Compute alpha values matching the original formula:
            # alpha = int(160 * (1.0 - y / max(1, top_gradient_h)))
            y_indices = np.arange(top_gradient_h, dtype=np.float32)
            denom_top = max(1, top_gradient_h)
            top_alphas = (160.0 * (1.0 - y_indices / float(denom_top))).clip(0, 255).astype(np.uint8)
            # Broadcast alphas across the width to form an RGBA image (RGB all zeros, varying alpha)
            top_gradient = np.zeros((top_gradient_h, width, 4), dtype=np.uint8)
            top_gradient[:, :, 3] = top_alphas[:, None]
            top_gradient_img = Image.fromarray(top_gradient, mode="RGBA")
            overlay.alpha_composite(top_gradient_img, (0, 0))

        # Create bottom gradient using vectorized numpy operations
        bottom_gradient_h = int(height * 0.28)
        if bottom_gradient_h > 0:
            # Compute alpha values matching the original formula:
            # for i in range(bottom_gradient_h):
            #     alpha = int(195 * (1.0 - i / max(1, bottom_gradient_h)))
            i_indices = np.arange(bottom_gradient_h, dtype=np.float32)
            denom_bottom = max(1, bottom_gradient_h)
            bottom_alphas = (195.0 * (1.0 - i_indices / float(denom_bottom))).clip(0, 255).astype(np.uint8)
            bottom_gradient = np.zeros((bottom_gradient_h, width, 4), dtype=np.uint8)
            bottom_gradient[:, :, 3] = bottom_alphas[:, None]
            bottom_gradient_img = Image.fromarray(bottom_gradient, mode="RGBA")
            bottom_y = height - bottom_gradient_h
            overlay.alpha_composite(bottom_gradient_img, (0, bottom_y))
        base.alpha_composite(overlay)

    def _draw_center_marker(self, draw: ImageDraw.ImageDraw, camera: CameraState) -> None:
        if self.config.style.ui_preset != "social_map":
            return
        x, y = latlon_to_screen_px(
            self.config.center.lat,
            self.config.center.lon,
            camera.zoom,
            camera.center_lat,
            camera.center_lon,
            self.config.style.width,
            self.config.style.height,
        )
        draw.ellipse((x - 28, y - 28, x + 28, y + 28), fill=(255, 255, 255, 235), outline=(255, 255, 255, 255), width=3)
        draw.ellipse((x - 16, y - 16, x + 16, y + 16), fill=(230, 22, 30, 255))
        text = self.config.style.social_center_label
        text_w, text_h = self.large_font.getbbox(text)[2:4]
        draw.text(
            (x - text_w / 2, y - 72 - text_h),
            text,
            font=self.large_font,
            fill=(255, 255, 255, 255),
            stroke_width=4,
            stroke_fill=(205, 22, 22, 255),
        )

    def _draw_social_chrome(self, draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
        bar_x1, bar_y1 = 28, 32
        bar_x2, bar_y2 = width - 28, 126
        draw.rounded_rectangle(
            (bar_x1, bar_y1, bar_x2, bar_y2),
            radius=20,
            outline=(255, 255, 255, 225),
            width=3,
            fill=(25, 25, 25, 65),
        )
        draw.text((46, 48), "<", font=self.large_font, fill=(255, 255, 255, 240))
        draw.ellipse((114, 58, 148, 92), outline=(255, 255, 255, 230), width=3)
        draw.line((141, 87, 153, 99), fill=(255, 255, 255, 230), width=3)
        draw.text((168, 58), self.config.style.social_search_left_text, font=self.font, fill=(255, 255, 255, 230))
        right_text = self.config.style.social_search_right_text
        text_w, _ = self.font.getbbox(right_text)[2:4]
        draw.text((width - 40 - text_w, 58), right_text, font=self.font, fill=(255, 255, 255, 230))

        rail_x = width - 62
        self._draw_profile_icon(draw, rail_x, height - 620)
        self._draw_heart_icon(draw, rail_x, height - 495)
        draw.text((rail_x - 20, height - 448), "991", font=self.small_font, fill=(255, 255, 255, 240))
        self._draw_chat_icon(draw, rail_x, height - 365)
        draw.text((rail_x - 20, height - 318), "145", font=self.small_font, fill=(255, 255, 255, 240))
        self._draw_bookmark_icon(draw, rail_x, height - 235)
        draw.text((rail_x - 20, height - 188), "539", font=self.small_font, fill=(255, 255, 255, 240))
        self._draw_share_icon(draw, rail_x, height - 105)
        draw.text((rail_x - 20, height - 58), "878", font=self.small_font, fill=(255, 255, 255, 240))

        bottom_y = height - 210
        draw.rectangle((0, bottom_y, width, height), fill=(0, 0, 0, 185))
        subtitle = self.config.style.subtitle or "A quick tour of local amenities"
        draw.text((24, bottom_y + 18), self.config.style.social_account_label, font=self.small_font, fill=(255, 255, 255, 230))
        draw.text((24, bottom_y + 56), subtitle, font=self.small_font, fill=(245, 245, 245, 220))

        comment_y = height - 102
        draw.rounded_rectangle((24, comment_y, width - 24, comment_y + 72), radius=35, fill=(18, 18, 18, 240))
        draw.text((52, comment_y + 19), "Add a comment...", font=self.small_font, fill=(205, 205, 205, 235))

    def _draw_profile_icon(self, draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
        draw.ellipse((x - 34, y - 34, x + 34, y + 34), fill=(210, 240, 255, 225))
        draw.ellipse((x - 14, y - 12, x + 14, y + 16), fill=(95, 145, 185, 255))
        draw.ellipse((x - 16, y + 20, x + 16, y + 28), fill=(95, 145, 185, 255))
        draw.ellipse((x - 16, y + 28, x + 16, y + 60), fill=(228, 26, 38, 255))
        draw.text((x - 8, y + 31), "+", font=self.small_font, fill=(255, 255, 255, 255))

    def _draw_heart_icon(self, draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
        draw.ellipse((x - 13, y - 8, x - 1, y + 5), fill=(255, 255, 255, 245))
        draw.ellipse((x + 1, y - 8, x + 13, y + 5), fill=(255, 255, 255, 245))
        draw.polygon([(x - 15, y + 0), (x + 15, y + 0), (x, y + 24)], fill=(255, 255, 255, 245))

    def _draw_chat_icon(self, draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
        draw.rounded_rectangle((x - 18, y - 14, x + 18, y + 14), radius=8, outline=(255, 255, 255, 245), width=3)
        draw.polygon([(x - 5, y + 14), (x + 3, y + 14), (x - 1, y + 22)], fill=(255, 255, 255, 245))

    def _draw_bookmark_icon(self, draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
        draw.polygon(
            [(x - 13, y - 20), (x + 13, y - 20), (x + 13, y + 22), (x, y + 10), (x - 13, y + 22)],
            outline=(255, 255, 255, 245),
            fill=None,
            width=3,
        )

    def _draw_share_icon(self, draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
        draw.polygon(
            [(x - 16, y + 15), (x + 4, y + 15), (x + 4, y + 25), (x + 22, y + 0), (x + 4, y - 25), (x + 4, y - 15), (x - 16, y - 15)],
            outline=(255, 255, 255, 245),
            fill=None,
            width=3,
        )

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
