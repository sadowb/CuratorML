from __future__ import annotations

import math
from typing import Iterable

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont

from app.services.psd_export.models import CanvasSize, TranslatedTextBlock


class RasterTextRenderer:
    """V1 raster text rendering for PSD export."""

    def render_text_block(self, canvas: CanvasSize, block: TranslatedTextBlock) -> np.ndarray:
        image = Image.new("RGBA", (canvas.width, canvas.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        color = self._parse_color(block.color)
        text = (block.translated_text or "").strip()
        if not text:
            return np.asarray(image)

        x = int(round(block.x))
        y = int(round(block.y))
        width = max(1, int(round(block.width)))
        height = max(1, int(round(block.height)))
        max_x = max(0, canvas.width - 1)
        max_y = max(0, canvas.height - 1)
        x = max(0, min(x, max_x))
        y = max(0, min(y, max_y))
        width = min(width, canvas.width - x)
        height = min(height, canvas.height - y)

        font = self._load_font(block.font_name, block.font_size, block.font_weight)
        wrapped = self._wrap_text(draw, text, font, width)
        line_height = int(math.ceil(font.size * 1.2))

        # Match editor behavior: repeatedly shrink until both width+height fit.
        for _ in range(32):
            max_line_width = 0
            for line in wrapped:
                bbox = draw.textbbox((0, 0), line, font=font)
                max_line_width = max(max_line_width, bbox[2] - bbox[0])
            total_height = line_height * max(len(wrapped), 1)
            if max_line_width <= width * 0.92 and total_height <= height * 0.92:
                break
            if font.size <= 8:
                break
            font = self._load_font(block.font_name, max(8, font.size - 1), block.font_weight)
            wrapped = self._wrap_text(draw, text, font, width)
            line_height = int(math.ceil(font.size * 1.2))

        max_line_width = 0
        for line in wrapped:
            bbox = draw.textbbox((0, 0), line, font=font)
            max_line_width = max(max_line_width, bbox[2] - bbox[0])
        total_height = line_height * max(len(wrapped), 1)

        # Center text block inside render bounds so persisted coordinates match preview.
        content_x = x + max(0, int(round((width - max_line_width) / 2)))
        current_y = y + max(0, int(round((height - total_height) / 2)))
        max_y = y + height

        for line in wrapped:
            if current_y >= max_y:
                break
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            line_x = x + max(0, int(round((width - line_width) / 2)))
            draw.text((line_x, current_y), line, fill=color, font=font)
            current_y += line_height
        return np.asarray(image)

    def render_ocr_notes(self, canvas: CanvasSize, blocks: Iterable[TranslatedTextBlock]) -> np.ndarray:
        image = Image.new("RGBA", (canvas.width, canvas.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        font = self._load_font(None, 14)
        for block in blocks:
            note = (block.ocr_text or "").strip()
            if not note:
                continue
            x = max(0, min(int(round(block.x)), canvas.width - 1))
            y = max(0, min(int(round(block.y)), canvas.height - 1))
            text = f"{block.name}: {note}"
            draw.text((x, y), text, fill=(25, 25, 25, 220), font=font)
        return np.asarray(image)

    def _parse_color(self, value: str) -> tuple[int, int, int, int]:
        rgb = ImageColor.getrgb(value)
        if len(rgb) == 4:
            return rgb
        return rgb[0], rgb[1], rgb[2], 255

    def _load_font(self, font_name: str | None, size: float, font_weight: str = "normal") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        resolved_size = max(8, int(round(size)))
        if font_name:
            try:
                return ImageFont.truetype(font_name, resolved_size)
            except OSError:
                pass
        fallbacks = ("Arial Bold.ttf", "DejaVuSans-Bold.ttf", "Arial.ttf", "DejaVuSans.ttf") if font_weight == "bold" else ("Arial.ttf", "DejaVuSans.ttf")
        for fallback in fallbacks:
            try:
                return ImageFont.truetype(fallback, resolved_size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _wrap_text(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
        if width <= 1:
            return [text]
        words = text.split()
        if not words:
            return [text]

        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if (bbox[2] - bbox[0]) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines
