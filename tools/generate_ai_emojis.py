"""Generate Xiaozhi-compatible Otto GIF expressions in ``gifs/``.

The drawings intentionally use the same visual vocabulary as the original Otto
assets: a 240 x 240 black display, white geometric eyes, antialiased edges, and
an 80 ms frame cadence. Run this file with Pillow installed to regenerate the
scripted standard expressions.
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


def stroke(
    canvas: Image.Image,
    points: list[tuple[float, float]],
    width: float,
    *,
    fill: int = FOREGROUND,
) -> None:
    scaled = [(round(x * SCALE), round(y * SCALE)) for x, y in points]
    line_width = max(1, round(width * SCALE))
    draw = ImageDraw.Draw(canvas)
    draw.line(scaled, fill=fill, width=line_width, joint="curve")
    radius = line_width / 2
    for x, y in (scaled[0], scaled[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def neutral_pair(canvas: Image.Image, amount: float) -> None:
    size = 78 * (1 - amount)
    if size >= 1:
        ellipse(canvas, 73, 120, size, size)
        ellipse(canvas, 167, 120, size, size)


def ring_eye(
    canvas: Image.Image,
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    pupil_x: float = 0,
    pupil_y: float = 0,
) -> None:
    ellipse(canvas, center_x, center_y, width, height)
    ellipse(canvas, center_x, center_y, width * 0.58, height * 0.62, fill=0)
    ellipse(canvas, center_x + pupil_x, center_y + pupil_y,
            width * 0.18, width * 0.18)


def sparkle(canvas: Image.Image, center_x: float, center_y: float,
            size: float) -> None:
    stroke(canvas, [(center_x - size, center_y), (center_x + size, center_y)], 4)
    stroke(canvas, [(center_x, center_y - size), (center_x, center_y + size)], 4)


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


def render_laughing(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()
    neutral_pair(canvas, amount)
    width = 61 * amount
    height = 50 * amount
    if width >= 2:
        bounce = 4 * amount * math.sin(phase * 6 * math.pi)
        for center_x in (73, 167):
            listening_arc(canvas,
                          (center_x - width / 2, 100 + bounce - height / 2,
                           center_x + width / 2, 100 + bounce + height / 2),
                          185, 355, 12 * amount)
        fall = (phase * 4 % 1) * 25
        ellipse(canvas, 37, 119 + fall, 10 * amount, 18 * amount)
        ellipse(canvas, 203, 132 + (25 - fall), 10 * amount, 18 * amount)
    return downsample(canvas)


def render_funny(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()
    neutral_pair(canvas, amount)
    wobble = 6 * amount * math.sin(phase * 4 * math.pi)
    if amount > 0.02:
        ellipse(canvas, 72, 116 + wobble, 78 * amount, 96 * amount)
        rounded_eye(canvas, 168, 125 - wobble / 2, 72 * amount,
                    max(2, 18 * amount), angle=-18 * amount)
        sparkle(canvas, 202, 78, 10 * amount)
    return downsample(canvas)


def render_crying(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()
    neutral_pair(canvas, amount)
    if amount > 0.02:
        rounded_eye(canvas, 73, 106, 70 * amount, max(2, 20 * amount),
                    angle=12 * amount)
        rounded_eye(canvas, 167, 106, 70 * amount, max(2, 20 * amount),
                    angle=-12 * amount)
        fall = (phase * 3 % 1) * 52
        for x, offset in ((59, 0), (83, 19), (153, 27), (177, 8)):
            y = 126 + ((fall + offset) % 52)
            ellipse(canvas, x, y, 10 * amount, 23 * amount)
    return downsample(canvas)


def render_shocked(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()
    neutral_pair(canvas, amount)
    if amount > 0.02:
        shake = 4 * amount * math.sin(phase * 12 * math.pi)
        ring_eye(canvas, 73 + shake, 120, 74 * amount, 98 * amount,
                 0, -5 * amount)
        ring_eye(canvas, 167 + shake, 120, 74 * amount, 98 * amount,
                 0, -5 * amount)
        sparkle(canvas, 120, 55, 9 * amount)
    return downsample(canvas)


def render_winking(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()
    neutral_pair(canvas, amount)
    if amount > 0.02:
        bounce = 3 * amount * math.sin(phase * 4 * math.pi)
        ellipse(canvas, 72, 117 + bounce, 72 * amount, 86 * amount)
        rounded_eye(canvas, 168, 122 - bounce, 72 * amount,
                    max(2, 16 * amount), angle=-10 * amount)
        sparkle(canvas, 210, 92, 9 * amount)
    return downsample(canvas)


def render_cool(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()
    neutral_pair(canvas, amount)
    if amount > 0.02:
        tilt = 2 * amount * math.sin(phase * 2 * math.pi)
        rounded_eye(canvas, 70, 118 + tilt, 82 * amount, 46 * amount,
                    angle=4 * amount, radius=12)
        rounded_eye(canvas, 170, 118 - tilt, 82 * amount, 46 * amount,
                    angle=-4 * amount, radius=12)
        stroke(canvas, [(109, 113), (131, 113)], 8 * amount)
        stroke(canvas, [(30, 102), (16, 94)], 5 * amount)
        stroke(canvas, [(210, 102), (224, 94)], 5 * amount)
    return downsample(canvas)


def render_relaxed(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()
    neutral_pair(canvas, amount)
    if amount > 0.02:
        drift = 4 * amount * math.sin(phase * 2 * math.pi)
        listening_arc(canvas, (39, 105 + drift, 107, 143 + drift),
                      10, 170, 10 * amount)
        listening_arc(canvas, (133, 105 + drift, 201, 143 + drift),
                      10, 170, 10 * amount)
    return downsample(canvas)


def render_delicious(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()
    neutral_pair(canvas, amount)
    if amount > 0.02:
        bounce = 3 * amount * math.sin(phase * 6 * math.pi)
        listening_arc(canvas, (39, 91 + bounce, 107, 145 + bounce),
                      185, 355, 11 * amount)
        rounded_eye(canvas, 168, 120 - bounce, 70 * amount,
                    max(2, 18 * amount), angle=-8 * amount)
        ellipse(canvas, 205, 145 + bounce, 13 * amount, 13 * amount)
    return downsample(canvas)


def render_kissy(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()
    neutral_pair(canvas, amount)
    if amount > 0.02:
        rounded_eye(canvas, 70, 119, 68 * amount, max(2, 17 * amount),
                    angle=8 * amount)
        rounded_eye(canvas, 157, 119, 68 * amount, max(2, 17 * amount),
                    angle=-8 * amount)
        rise = 18 * amount * math.sin(math.pi * phase)
        heart(canvas, 207, 125 - rise, 28 * amount, 26 * amount)
    return downsample(canvas)


def render_confident(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()
    neutral_pair(canvas, amount)
    if amount > 0.02:
        lift = 4 * amount * math.sin(phase * 2 * math.pi)
        rounded_eye(canvas, 73, 119 - lift, 76 * amount,
                    max(2, 25 * amount), angle=-8 * amount)
        rounded_eye(canvas, 167, 115 + lift, 76 * amount,
                    max(2, 25 * amount), angle=8 * amount)
    return downsample(canvas)


def render_silly(frame_index: int) -> Image.Image:
    amount = expression_amount(frame_index)
    phase = frame_index / (FRAME_COUNT - 1)
    canvas = new_canvas()
    neutral_pair(canvas, amount)
    if amount > 0.02:
        roam = 8 * amount * math.sin(phase * 4 * math.pi)
        ring_eye(canvas, 73, 113, 72 * amount, 80 * amount,
                 10 * amount, roam)
        ring_eye(canvas, 167, 127, 72 * amount, 80 * amount,
                 -10 * amount, -roam)
    return downsample(canvas)


RENDERERS: dict[str, Callable[[int], Image.Image]] = {
    "thinking": render_thinking,
    "confused": render_confused,
    "loving": render_love,
    "sleepy": render_sleepy,
    "laughing": render_laughing,
    "funny": render_funny,
    "crying": render_crying,
    "shocked": render_shocked,
    "winking": render_winking,
    "cool": render_cool,
    "relaxed": render_relaxed,
    "delicious": render_delicious,
    "kissy": render_kissy,
    "confident": render_confident,
    "silly": render_silly,
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
