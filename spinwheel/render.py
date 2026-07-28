"""Pillow rendering helpers for SpinWheel."""

from __future__ import annotations

import io
import math
from functools import lru_cache
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from collections.abc import Sequence

WHEEL_SIZE = 560
BACKGROUND = "#111827"


@lru_cache(maxsize=16)
def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        (
            "DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        )
        if bold
        else (
            "DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "C:/Windows/Fonts/arial.ttf",
        )
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _contrast(hex_color: str) -> str:
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
    luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
    return "#111827" if luminance > 165 else "#ffffff"


@lru_cache(maxsize=512)
def _label_tile(
    label: str,
    maximum_width: int,
    preferred_size: int,
    text_color: str,
) -> Image.Image:
    """Build one reusable transparent label, shrinking or trimming as needed."""
    measuring = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    font_size = preferred_size
    rendered = label

    while font_size > 10:
        font = _font(font_size, bold=True)
        box = measuring.textbbox((0, 0), rendered, font=font, stroke_width=2)
        if box[2] - box[0] <= maximum_width:
            break
        font_size -= 1

    font = _font(font_size, bold=True)
    stroke_width = 2 if font_size >= 18 else 1
    while len(rendered) > 2:
        box = measuring.textbbox((0, 0), rendered, font=font, stroke_width=stroke_width)
        if box[2] - box[0] <= maximum_width:
            break
        rendered = f"{rendered[:-2]}…"

    stroke_color = "#f8fafc" if text_color == "#111827" else "#020617"
    box = measuring.textbbox((0, 0), rendered, font=font, stroke_width=stroke_width)
    width = box[2] - box[0]
    height = box[3] - box[1]
    padding = 5
    tile = Image.new("RGBA", (width + (padding * 2), height + (padding * 2)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)
    draw.text(
        (padding - box[0], padding - box[1]),
        rendered,
        font=font,
        fill=text_color,
        stroke_fill=stroke_color,
        stroke_width=stroke_width,
    )
    return tile


def render_wheel(
    entries: Sequence[str],
    colors: Sequence[str],
    *,
    rotation: float = 0.0,
    winner_index: int | None = None,
    pointer: bool = True,
    size: int = WHEEL_SIZE,
) -> Image.Image:
    """Render one wheel frame with a clockwise rotation in degrees."""
    image = Image.new("RGB", (size, size), BACKGROUND)
    draw = ImageDraw.Draw(image)
    center = size / 2
    radius = (size * 0.42) if pointer else (size * 0.45)
    bounds = (
        int(center - radius),
        int(center - radius),
        int(center + radius),
        int(center + radius),
    )
    segment = 360.0 / len(entries)

    # Soft concentric borders give the wheel depth without making GIFs enormous.
    draw.ellipse(
        (bounds[0] - 10, bounds[1] - 10, bounds[2] + 10, bounds[3] + 10),
        fill="#030712",
        outline="#64748b",
        width=3,
    )
    for index, entry in enumerate(entries):
        start = (index * segment) + rotation
        end = start + segment
        fill = colors[index % len(colors)]
        outline = "#fef3c7" if winner_index == index else "#f8fafc"
        width = 6 if winner_index == index else 2
        draw.pieslice(bounds, start=start, end=end, fill=fill, outline=outline, width=width)

        angle = math.radians(start + (segment / 2))
        text_radius = radius * (0.63 if len(entries) <= 16 else 0.67)
        x = center + (math.cos(angle) * text_radius)
        y = center + (math.sin(angle) * text_radius)
        arc_width = math.radians(segment) * text_radius
        preferred_size = min(30, max(10, int(arc_width * 0.72)))
        label_tile = _label_tile(
            entry,
            int(radius * 0.72),
            preferred_size,
            _contrast(fill),
        )
        display_angle = (start + (segment / 2)) % 360
        if 90 < display_angle < 270:
            display_angle += 180
        rotated_label = label_tile.rotate(
            -display_angle,
            resample=Image.Resampling.BICUBIC,
            expand=True,
        )
        image.paste(
            rotated_label,
            (int(x - (rotated_label.width / 2)), int(y - (rotated_label.height / 2))),
            rotated_label,
        )

    hub_radius = max(29, int(radius * 0.13))
    draw.ellipse(
        (
            int(center - hub_radius),
            int(center - hub_radius),
            int(center + hub_radius),
            int(center + hub_radius),
        ),
        fill="#f8fafc",
        outline="#0f172a",
        width=5,
    )
    draw.ellipse(
        (
            int(center - 10),
            int(center - 10),
            int(center + 10),
            int(center + 10),
        ),
        fill="#f59e0b",
    )

    if pointer:
        tip_x = int(center + radius - 4)
        base_x = min(size - 4, tip_x + 58)
        draw.polygon(
            [(tip_x, int(center)), (base_x, int(center - 28)), (base_x, int(center + 28))],
            fill="#fbbf24",
            outline="#fff7ed",
        )
    return image


def winner_rotation(winner_index: int, entry_count: int, turns: int) -> float:
    """Return a positive clockwise rotation that centers a winner at the pointer."""
    segment = 360.0 / entry_count
    center_angle = (winner_index + 0.5) * segment
    return (turns * 360.0) - center_angle


def render_png(
    entries: Sequence[str],
    colors: Sequence[str],
    *,
    rotation: float = 0.0,
    winner_index: int | None = None,
    pointer: bool = True,
) -> bytes:
    """Render a static PNG."""
    image = render_wheel(
        entries,
        colors,
        rotation=rotation,
        winner_index=winner_index,
        pointer=pointer,
    )
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def render_spin_gif(
    entries: Sequence[str],
    colors: Sequence[str],
    winner_index: int,
    *,
    turns: int,
    frame_count: int = 42,
    size: int = WHEEL_SIZE,
) -> bytes:
    """Render an easing animated GIF that stops on ``winner_index``."""
    final_rotation = winner_rotation(winner_index, len(entries), turns)
    frames: list[Image.Image] = []
    for frame_index in range(frame_count):
        progress = frame_index / (frame_count - 1)
        eased = 1.0 - ((1.0 - progress) ** 3)
        rotation = final_rotation * eased
        highlight = winner_index if frame_index >= frame_count - 3 else None
        frame = render_wheel(
            entries,
            colors,
            rotation=rotation,
            winner_index=highlight,
            size=size,
        )
        frames.append(frame.quantize(colors=128, method=Image.Quantize.MEDIANCUT))

    output = io.BytesIO()
    durations = [75] * (frame_count - 1) + [1200]
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        optimize=True,
        disposal=2,
    )
    return output.getvalue()
