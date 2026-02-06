from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


@dataclass
class LabelPlacement:
    text: str
    position: Tuple[int, int]
    box: Tuple[int, int, int, int]


def load_font(font_path: Optional[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if font_path:
        try:
            return ImageFont.truetype(font_path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_pin(draw: ImageDraw.ImageDraw, x: int, y: int, color: Tuple[int, int, int]) -> None:
    radius = 12
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color, outline=(255, 255, 255))
    draw.polygon([(x, y + 20), (x - 10, y), (x + 10, y)], fill=color)


def draw_ring(draw: ImageDraw.ImageDraw, x: int, y: int, radius: int, alpha: int) -> None:
    ring = Image.new("RGBA", (radius * 2 + 2, radius * 2 + 2), (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(ring)
    ring_draw.ellipse((1, 1, radius * 2, radius * 2), outline=(255, 255, 255, alpha), width=3)
    draw.bitmap((x - radius, y - radius), ring, fill=None)


def layout_labels(
    base: Image.Image,
    labels: Iterable[Tuple[str, Tuple[int, int]]],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    padding: int = 8,
    max_shift: int = 80,
) -> List[LabelPlacement]:
    placements: List[LabelPlacement] = []
    for text, (x, y) in labels:
        width, height = font.getbbox(text)[2:4]
        shift = 0
        while shift <= max_shift:
            left = x + 16
            top = y - height - 8 + shift
            box = (left - padding, top - padding, left + width + padding, top + height + padding)
            if not any(_overlaps(box, placement.box) for placement in placements):
                placements.append(LabelPlacement(text=text, position=(left, top), box=box))
                break
            shift += 18
    return placements


def _overlaps(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])
