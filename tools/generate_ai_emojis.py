"""Generate the AI interaction GIFs in ``gifs/``.

The drawings intentionally use the same visual vocabulary as the original Otto
assets: a 240 x 240 black display, white geometric eyes, antialiased edges, and
an 80 ms frame cadence.  Run this file with Pillow installed to regenerate the
six AI-specific animations.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw


SIZE = 240
SCALE = 4
FRAME_COUNT = 33
FRAME_DURATION_MS = 80
BACKGROUND = (0, 0, 0)
FOREGROUND = 255

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "gifs"


def lerp(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def ease(value: float) -> float:
    """Smoothstep keeps the neutral-to-expression transition gentle."""
    return value * value * (3.0 - 2.0 * value)


def expression_amount(frame_index: int) -> float:
    phase = frame_index / (FRAME_COUNT - 1)
    return ease(math.sin(math.pi * phase))


def new_canvas() -> Image.Image:
    return Image.new("L", (SIZE * SCALE, SIZE * SCALE), 0)


def downsample(mask: Image.Image) -> Image.Image:
    small = mask.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    return Image.merge("RGB", (small, small, small))


def ellipse(
    canvas: Image.Image,
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    *,
    fill: int = FOREGROUND,
) -> None:
    draw = ImageDraw.Draw(canvas)
    x0 = (center_x - width / 2) * SCALE
    y0 = (center_y - height / 2) * SCALE
    x1 = (center_x + width / 2) * SCALE
    y1 = (center_y + height / 2) * SCALE
    draw.ellipse((x0, y0, x1, y1), fill=fill)


def rounded_eye(
    canvas: Image.Image,
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    *,
    angle: float = 0.0,
    radius: float | None = None,
    fill: int = FOREGROUND,
) -> None:
    """Draw a rotatable rounded eye on the high-resolution mask."""
    pad = 12 * SCALE
    local_width = max(1, round(width * SCALE))
    local_height = max(1, round(height * SCALE))
    local = Image.new("L", (local_width + pad * 2, local_height + pad * 2), 0)
    draw = ImageDraw.Draw(local)
    corner = min(width, height) / 2 if radius is None else radius
    draw.rounded_rectangle(
        (pad, pad, pad + local_width, pad + local_height),
        radius=max(1, round(corner * SCALE)),
        fill=fill,
    )
    if angle:
        local = local.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    left = round(center_x * SCALE - local.width / 2)
    top = round(center_y * SCALE - local.height / 2)
    canvas.paste(local, (left, top), local)


def heart(
    canvas: Image.Image,
    center_x: float,
    center_y: float,
    width: float,
    height: float,
) -> None:
    """Draw a smooth parametric heart without fonts or external assets."""
    points: list[tuple[float, float]] = []
    samples: list[tuple[float, float]] = []
    for index in range(160):
        t = 2 * math.pi * index / 160
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        samples.append((x, -y))
    min_x = min(point[0] for point in samples)
    max_x = max(point[0] for point in samples)
    min_y = min(point[1] for point in samples)
    max_y = max(point[1] for point in samples)
    for x, y in samples:
        px = center_x + ((x - min_x) / (max_x - min_x) - 0.5) * width
        py = center_y + ((y - min_y) / (max_y - min_y) - 0.5) * height
        points.append((px * SCALE, py * SCALE))
    ImageDraw.Draw(canvas).polygon(points, fill=FOREGROUND)


def listening_arc(
    canvas: Image.Image,
    bounds: tuple[float, float, float, float],
    start: int,
    end: int,
    width: float,
) -> None:
    scaled = tuple(value * SCALE for value in bounds)
    ImageDraw.Draw(canvas).arc(
        scaled,
        start=start,
        end=end,
        fill=FOREGROUND,
        width=max(1, round(width * SCALE)),
    )


def render_thinking(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()

    dot_width = lerp(78, 30, amount)
    x_left = lerp(73, 82, amount)
    x_right = lerp(167, 158, amount)
    bounce_left = 5 * amount * math.sin(phase * 4 * math.pi)
    bounce_right = 5 * amount * math.sin(phase * 4 * math.pi + 2 * math.pi / 3)
    ellipse(canvas, x_left, 120 + bounce_left, dot_width, dot_width)
    ellipse(canvas, x_right, 120 + bounce_right, dot_width, dot_width)

    center_size = 30 * amount
    if center_size >= 1:
        bounce_center = 5 * amount * math.sin(phase * 4 * math.pi + 4 * math.pi / 3)
        ellipse(canvas, 120, 120 + bounce_center, center_size, center_size)
    return downsample(canvas)


def render_listening(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    pulse = 1 + 0.04 * amount * math.sin(phase * 6 * math.pi)
    follow = 2.5 * amount * math.sin(phase * 2 * math.pi)
    canvas = new_canvas()

    eye_width = lerp(78, 57, amount) * pulse
    eye_height = lerp(76, 96, amount) * pulse
    ellipse(canvas, lerp(73, 82, amount) + follow, 120, eye_width, eye_height)
    ellipse(canvas, lerp(167, 158, amount) + follow, 120, eye_width, eye_height)

    if amount > 0.18:
        arc_width = lerp(0, 6, (amount - 0.18) / 0.82)
        listening_arc(canvas, (16, 72, 70, 168), 110, 250, arc_width)
        listening_arc(canvas, (170, 72, 224, 168), -70, 70, arc_width)
    return downsample(canvas)


def render_speaking(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()

    rhythm_left = (math.sin(phase * 10 * math.pi) + 1) / 2
    rhythm_right = (math.sin(phase * 10 * math.pi + math.pi) + 1) / 2
    left_height = lerp(76, lerp(46, 94, rhythm_left), amount)
    right_height = lerp(76, lerp(46, 94, rhythm_right), amount)
    eye_width = lerp(78, 58, amount)
    rounded_eye(canvas, 76, 120, eye_width, left_height)
    rounded_eye(canvas, 164, 120, eye_width, right_height)
    return downsample(canvas)


def render_confused(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    wobble = 4 * amount * math.sin(phase * 4 * math.pi)
    canvas = new_canvas()

    left_width = lerp(78, 91, amount)
    left_height = lerp(76, 91, amount)
    ellipse(canvas, 73, 116 + wobble, left_width, left_height)

    right_width = lerp(78, 69, amount)
    right_height = lerp(76, 30, amount)
    rounded_eye(
        canvas,
        167,
        125 - wobble / 2,
        right_width,
        right_height,
        angle=lerp(0, -16, amount),
    )
    return downsample(canvas)


def render_love(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    pulse = 1 + 0.055 * amount * math.sin(phase * 6 * math.pi)
    canvas = new_canvas()

    # Cross-fading through size rather than opacity keeps the bold monochrome look.
    neutral_size = 78 * (1 - amount)
    if neutral_size >= 1:
        ellipse(canvas, 73, 120, neutral_size, neutral_size)
        ellipse(canvas, 167, 120, neutral_size, neutral_size)
    heart_width = 75 * amount * pulse
    heart_height = 69 * amount * pulse
    if heart_width >= 1:
        heart(canvas, 73, 120, heart_width, heart_height)
        heart(canvas, 167, 120, heart_width, heart_height)
    return downsample(canvas)


def render_sleepy(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    drift = 3 * amount * math.sin(phase * 2 * math.pi)
    canvas = new_canvas()

    eye_width = lerp(78, 75, amount)
    eye_height = lerp(76, 17, amount)
    rounded_eye(
        canvas,
        73,
        lerp(120, 139, amount) + drift,
        eye_width,
        eye_height,
        angle=lerp(0, 8, amount),
    )
    rounded_eye(
        canvas,
        167,
        lerp(120, 139, amount) + drift,
        eye_width,
        eye_height,
        angle=lerp(0, -8, amount),
    )
    return downsample(canvas)


RENDERERS: dict[str, Callable[[int], Image.Image]] = {
    "thinking": render_thinking,
    "listening": render_listening,
    "speaking": render_speaking,
    "confused": render_confused,
    "loving": render_love,
    "sleepy": render_sleepy,
}


def save_gif(name: str, renderer: Callable[[int], Image.Image]) -> Path:
    frames = [renderer(index) for index in range(FRAME_COUNT)]
    output_path = OUTPUT_DIR / f"{name}.gif"
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        disposal=2,
        optimize=True,
    )
    return output_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, renderer in RENDERERS.items():
        path = save_gif(name, renderer)
        print(f"generated {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
