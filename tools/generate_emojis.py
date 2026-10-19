"""Generate every Otto GIF expression in ``gifs/``.

All 21 Xiaozhi-standard expressions are drawn procedurally with Pillow; no
hand-made source assets are needed. Each eye is described by a handful of
numbers (size, tilt, eyelids, pupil, heart morph, ...), so an expression is a
target pose plus some idle motion, and every transition is a smooth parameter
morph rather than a cross-fade.

Conventions shared by every GIF:

* 240 x 240 canvas, white geometry on black, 4x supersampled antialiasing
* 16-level grayscale palette, 80 ms per frame, infinite loop
* the loop starts on the neutral face and eases back to it, so switching
  expressions and looping are both seamless
* delta frames (disposal 1 + transparency) keep the files small in flash

Usage::

    pip install pillow
    python tools/generate_emojis.py              # every expression
    python tools/generate_emojis.py happy sad    # only the named ones
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Callable

from PIL import Image, ImageChops, ImageDraw


SIZE = 240
SCALE = 4
FRAME_DURATION_MS = 80
GRAY_LEVELS = 16
STROKE = 12            # thickness of closed eyes and other line work
EYE_SIZE = 76
LEFT_X = 72.0
RIGHT_X = 168.0
EYE_Y = 120.0

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "gifs"


# --------------------------------------------------------------------------
# Timing helpers. ``t`` is the loop position in [0, 1).
# --------------------------------------------------------------------------

def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def lerp(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def smooth(value: float) -> float:
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


def pop(value: float, overshoot: float = 1.7) -> float:
    """Ease-out with a small overshoot, for expressions that snap open."""
    value = clamp(value) - 1.0
    return 1.0 + value * value * ((overshoot + 1.0) * value + overshoot)


def wave(t: float, cycles: float, phase: float = 0.0) -> float:
    return math.sin(2.0 * math.pi * (cycles * t + phase))


def window(t: float, start: float, end: float, ramp: float = 0.3) -> float:
    """Smooth bump that is 1 in the middle of [start, end] and 0 outside."""
    if t <= start or t >= end:
        return 0.0
    span = (end - start) * ramp
    return smooth(min((t - start) / span, (end - t) / span))


def blink(t: float, at: float, length: float = 0.08) -> float:
    """1 while the eyes are shut for a blink centred on ``at``."""
    distance = abs(t - at) / (length / 2)
    return smooth(1.0 - distance) if distance < 1.0 else 0.0


def envelope(
    t: float,
    attack: float = 0.18,
    release: float = 0.16,
    ease: Callable[[float], float] = smooth,
) -> float:
    """Expression strength: 0 at the neutral loop boundary, 1 while holding."""
    if t < attack:
        return ease(t / attack)
    if t > 1.0 - release:
        return smooth((1.0 - t) / release)
    return 1.0


def cycle(t: float, cycles: int, offset: float = 0.0) -> float:
    """Sawtooth in [0, 1) that repeats a whole number of times per loop."""
    return (cycles * t + offset) % 1.0


# --------------------------------------------------------------------------
# Eye model
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Eye:
    """One eye in 240 px face coordinates.

    ``tilt`` and ``lid_slant`` are measured towards the nose: positive values
    lower the inner corner (angry), negative values raise it (sad). ``bend``
    and ``kink`` shape a closed eye (``open == 0``) and must stay zero while
    the eye is open; use :func:`pose` to morph into closed targets.
    """

    x: float
    y: float = EYE_Y
    w: float = EYE_SIZE
    h: float = EYE_SIZE
    round: float = 1.0      # 1 = ellipse / pill, smaller = squarer corners
    tilt: float = 0.0       # rotation in degrees
    open: float = 1.0       # 0 = closed into a stroke
    lid: float = 0.0        # upper-lid coverage as a fraction of height
    lid_slant: float = 0.0  # upper-lid angle in degrees
    cheek: float = 0.0      # curved lower-lid coverage (happy crescent)
    hole: float = 0.0       # black pupil or ring opening, fraction of size
    hole_x: float = 0.0
    hole_y: float = 0.0
    glint: float = 0.0      # white dot inside the opening, diameter in px
    glint_x: float = 0.0
    glint_y: float = 0.0
    heart: float = 0.0      # 0 = round eye, 1 = heart
    shine: float = -1.0     # lens reflection position in [0, 1], else hidden
    bend: float = 0.0       # closed eye: + is U-shaped, - is n-shaped
    kink: float = 0.0       # closed eye: chevron half-height, apex inwards


LEFT = Eye(LEFT_X)
RIGHT = Eye(RIGHT_X)


def mix(start: Eye, end: Eye, amount: float) -> Eye:
    return Eye(**{
        item.name: lerp(getattr(start, item.name), getattr(end, item.name), amount)
        for item in fields(Eye)
    })


def pose(start: Eye, target: Eye, amount: float) -> Eye:
    """Morph towards ``target``; closed targets first shut, then bend."""
    if target.open > 0 or (target.bend == 0 and target.kink == 0):
        return mix(start, target, amount)
    shut = mix(start, replace(target, bend=0.0, kink=0.0), clamp(amount * 2))
    shape = clamp(amount * 2 - 1)
    return replace(shut, bend=target.bend * shape, kink=target.kink * shape)


def both(spread: float = 0.0, **values: float) -> tuple[Eye, Eye]:
    """A symmetric pair; ``spread`` moves the eyes apart (or together)."""
    return (Eye(LEFT_X - spread, **values), Eye(RIGHT_X + spread, **values))


def moved(eye: Eye, dx: float = 0.0, dy: float = 0.0) -> Eye:
    return replace(eye, x=eye.x + dx, y=eye.y + dy)


def scaled(eye: Eye, factor: float) -> Eye:
    return replace(eye, w=eye.w * factor, h=eye.h * factor)


def shut(eye: Eye, amount: float) -> Eye:
    return replace(eye, open=eye.open * (1.0 - amount)) if amount else eye


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------

Point = tuple[float, float]


class Painter:
    """Supersampled monochrome canvas with an optional whole-face offset."""

    def __init__(self, dx: float = 0.0, dy: float = 0.0) -> None:
        self.canvas = self.layer()
        self.dx = dx
        self.dy = dy

    @staticmethod
    def layer() -> Image.Image:
        return Image.new("L", (SIZE * SCALE, SIZE * SCALE), 0)

    def point(self, x: float, y: float) -> Point:
        return ((x + self.dx) * SCALE, (y + self.dy) * SCALE)

    def points(self, points: list[Point]) -> list[Point]:
        return [self.point(x, y) for x, y in points]

    def polygon(self, points: list[Point], *, fill: int = 255,
                target: Image.Image | None = None) -> None:
        ImageDraw.Draw(target or self.canvas).polygon(self.points(points), fill=fill)

    def ellipse(self, x: float, y: float, w: float, h: float, *, fill: int = 255,
                target: Image.Image | None = None) -> None:
        if w <= 0 or h <= 0:
            return
        x0, y0 = self.point(x - w / 2, y - h / 2)
        x1, y1 = self.point(x + w / 2, y + h / 2)
        ImageDraw.Draw(target or self.canvas).ellipse((x0, y0, x1, y1), fill=fill)

    def stroke(self, points: list[Point], width: float, *, fill: int = 255,
               target: Image.Image | None = None) -> None:
        if width <= 0.2:
            return
        draw = ImageDraw.Draw(target or self.canvas)
        scaled_points = self.points(points)
        line_width = max(1, round(width * SCALE))
        if len(scaled_points) > 1:
            draw.line(scaled_points, fill=fill, width=line_width, joint="curve")
        radius = line_width / 2
        for x, y in scaled_points:
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)

    def merge(self, layer: Image.Image) -> None:
        self.canvas = ImageChops.lighter(self.canvas, layer)

    def frame(self) -> Image.Image:
        small = self.canvas.resize((SIZE, SIZE), Image.Resampling.BOX)
        step = 255 / (GRAY_LEVELS - 1)
        indexed = small.point(lambda value: round(value / step))
        frame = Image.frombytes("P", indexed.size, indexed.tobytes())
        frame.putpalette(GRAY_PALETTE)
        return frame


GRAY_PALETTE = [
    round(level * 255 / (GRAY_LEVELS - 1))
    for level in range(GRAY_LEVELS)
    for _ in range(3)
]
# The global colour table gets spare slots; the first one (index GRAY_LEVELS)
# marks the unchanged pixels of delta frames as transparent.
GIF_PALETTE = bytes(GRAY_PALETTE + [0, 0, 0] * GRAY_LEVELS)


def rotate(points: list[Point], cx: float, cy: float, degrees: float) -> list[Point]:
    if not degrees:
        return points
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)
    return [
        (cx + (x - cx) * cos - (y - cy) * sin, cy + (x - cx) * sin + (y - cy) * cos)
        for x, y in points
    ]


def rounded_outline(cx: float, cy: float, w: float, h: float,
                    roundness: float, steps: int = 16) -> list[Point]:
    """Rounded rectangle with elliptical corners (an ellipse at roundness 1)."""
    ry = roundness * h / 2
    rx = roundness * (w / 2 if w <= h else min(w / 2, 0.8 * h))
    half_x, half_y = w / 2 - rx, h / 2 - ry
    outline = []
    for qx, qy, start in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        for index in range(steps + 1):
            angle = math.radians(start + 90 * index / steps)
            outline.append((cx + qx * half_x + rx * math.cos(angle),
                            cy + qy * half_y + ry * math.sin(angle)))
    return outline


def _heart_unit(samples: int) -> list[Point]:
    raw = []
    for index in range(samples):
        t = 2 * math.pi * index / samples
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        raw.append((x, -y))
    min_x = min(x for x, _ in raw)
    max_x = max(x for x, _ in raw)
    min_y = min(y for _, y in raw)
    max_y = max(y for _, y in raw)
    return [((x - min_x) / (max_x - min_x) - 0.5, (y - min_y) / (max_y - min_y) - 0.5)
            for x, y in raw]


HEART_SAMPLES = 96
HEART_UNIT = _heart_unit(HEART_SAMPLES)


def heart_outline(cx: float, cy: float, w: float, h: float,
                  amount: float = 1.0) -> list[Point]:
    """Heart outline; ``amount`` < 1 blends it with an ellipse of the same box."""
    outline = []
    for index, (hx, hy) in enumerate(HEART_UNIT):
        t = 2 * math.pi * index / HEART_SAMPLES
        ex, ey = 0.5 * math.sin(t), -0.5 * math.cos(t)
        outline.append((cx + lerp(ex, hx, amount) * w, cy + lerp(ey, hy, amount) * h))
    return outline


def draw_eye(painter: Painter, eye: Eye, side: int) -> None:
    """``side`` is +1 for the left eye and -1 for the right (towards the nose)."""
    angle = eye.tilt * side
    if eye.open <= 0.001:
        draw_closed_eye(painter, eye, side, angle)
        return

    layer = painter.layer()
    height = lerp(STROKE, eye.h, eye.open)
    if eye.heart > 0:
        outline = heart_outline(eye.x, eye.y, eye.w, height, eye.heart)
    else:
        outline = rounded_outline(eye.x, eye.y, eye.w, height, eye.round)
    painter.polygon(outline, target=layer)

    if eye.hole > 0:
        painter.ellipse(eye.x + eye.hole_x, eye.y + eye.hole_y,
                        eye.hole * eye.w, eye.hole * height, fill=0, target=layer)
    if eye.glint > 0:
        painter.ellipse(eye.x + eye.glint_x, eye.y + eye.glint_y,
                        eye.glint, eye.glint, target=layer)

    lid = eye.lid * eye.open
    slant = eye.lid_slant * eye.open
    if lid > 0 or slant:
        slope = math.tan(math.radians(slant)) * side
        top = eye.y - height / 2
        lid_y = top + lid * height
        reach = eye.w * 2
        painter.polygon([
            (eye.x - reach, lid_y - slope * reach),
            (eye.x + reach, lid_y + slope * reach),
            (eye.x + reach, top - 2 * reach),
            (eye.x - reach, top - 2 * reach),
        ], fill=0, target=layer)

    cheek = eye.cheek * eye.open
    if cheek > 0:
        cut_w, cut_h = eye.w * 1.25, height * 1.1
        cut_top = eye.y + height / 2 - cheek * height
        painter.ellipse(eye.x, cut_top + cut_h / 2, cut_w, cut_h, fill=0, target=layer)

    if 0.0 <= eye.shine <= 1.0:
        centre = lerp(eye.x - eye.w / 2 - 24, eye.x + eye.w / 2 + 24, eye.shine)
        for offset, width in ((0, 7), (12, 3)):
            x = centre + offset
            band = [(x - 18, eye.y + 40), (x + 18, eye.y - 40)]
            painter.stroke(band, width, fill=0, target=layer)

    if angle:
        layer = layer.rotate(-angle, resample=Image.Resampling.BICUBIC,
                             center=painter.point(eye.x, eye.y))
    painter.merge(layer)


def draw_closed_eye(painter: Painter, eye: Eye, side: int, angle: float) -> None:
    half = eye.w / 2 - STROKE / 2
    if eye.kink:
        outer = eye.x - side * half
        line = [(outer, eye.y - eye.kink), (eye.x + side * half, eye.y),
                (outer, eye.y + eye.kink)]
    else:
        line = [(eye.x + half * u, eye.y + eye.bend * (1 - u * u))
                for u in (index / 12 - 1 for index in range(25))]
    painter.stroke(rotate(line, eye.x, eye.y, angle), STROKE)


# --------------------------------------------------------------------------
# Decorations
# --------------------------------------------------------------------------

def heart(painter: Painter, x: float, y: float, size: float) -> None:
    if size > 0.5:
        painter.polygon(heart_outline(x, y, size, size * 0.92))


def drop(painter: Painter, x: float, y: float, radius: float,
         stretch: float = 2.3) -> None:
    """Tear drop with its round end centred on (x, y), pointing up."""
    if radius <= 0.3:
        return
    distance = radius * stretch
    edge = math.asin(radius / distance)
    start, end = -math.pi / 2 + (math.pi / 2 - edge), 3 * math.pi / 2 - (math.pi / 2 - edge)
    arc = [(x + radius * math.cos(lerp(start, end, i / 20)),
            y + radius * math.sin(lerp(start, end, i / 20))) for i in range(21)]
    painter.polygon([(x, y - distance)] + arc)


def sparkle(painter: Painter, x: float, y: float, size: float) -> None:
    if size <= 0.5:
        return
    star = []
    for index in range(8):
        radius = size if index % 2 == 0 else size * 0.32
        angle = math.pi / 4 * index
        star.append((x + radius * math.sin(angle), y - radius * math.cos(angle)))
    painter.polygon(star)


def letter_z(painter: Painter, x: float, y: float, size: float) -> None:
    if size > 0.5:
        painter.stroke([(x - size, y - size), (x + size, y - size),
                        (x - size, y + size), (x + size, y + size)], size * 0.45)


def question_mark(painter: Painter, x: float, y: float, size: float) -> None:
    if size <= 0.5:
        return
    hook = [(x + size * math.cos(a), y + size * math.sin(a))
            for a in (math.pi + (2.6 * math.pi / 2) * i / 16 for i in range(17))]
    hook += [(x, y + size * 1.5)]
    painter.stroke(hook, size * 0.55)
    painter.ellipse(x, y + size * 2.35, size * 0.62, size * 0.62)


def anger_mark(painter: Painter, x: float, y: float, size: float) -> None:
    """The four curved corners of the manga anger vein."""
    if size <= 0.5:
        return
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = x + sx * size * 0.95, y + sy * size * 0.95
            facing = math.atan2(-sy, -sx)
            arc = [(cx + size * 0.62 * math.cos(facing + math.radians(a)),
                    cy + size * 0.62 * math.sin(facing + math.radians(a)))
                   for a in range(-50, 51, 10)]
            painter.stroke(arc, size * 0.3)


def blush(painter: Painter, x: float, y: float, amount: float, t: float) -> None:
    for index in range(3):
        length = 7 * amount * (1 + 0.15 * wave(t, 4, index / 3))
        cx = x + (index - 1) * 12
        painter.stroke([(cx - length * 0.5, y + length), (cx + length * 0.5, y - length)],
                       4.5 * amount)


# --------------------------------------------------------------------------
# Expressions
# --------------------------------------------------------------------------

@dataclass
class Face:
    left: Eye = LEFT
    right: Eye = RIGHT
    dx: float = 0.0
    dy: float = 0.0
    extras: list[Callable[[Painter], None]] = field(default_factory=list)


def neutral(t: float) -> Face:
    look_right = window(t, 0.12, 0.40)
    look_left = window(t, 0.62, 0.90)
    look = 12 * look_right - 12 * look_left
    lift = -4 * look_left
    breathe = 1 + 0.012 * wave(t, 2)
    closed = blink(t, 0.5)
    left = shut(moved(scaled(LEFT, breathe * (1 - 0.003 * look)), look, lift), closed)
    right = shut(moved(scaled(RIGHT, breathe * (1 + 0.003 * look)), look, lift), closed)
    return Face(left, right)


def happy(t: float) -> Face:
    amount = envelope(t)
    left, right = both(y=EYE_Y - 8, w=82, h=80, cheek=0.5)
    bounce = -4 * abs(wave(t, 2)) * amount
    return Face(pose(LEFT, left, amount), pose(RIGHT, right, amount), dy=bounce)


def laughing(t: float) -> Face:
    amount = envelope(t, 0.2)
    left, right = both(y=EYE_Y - 4, w=60, open=0, kink=20)
    squeeze = 1 + 0.18 * wave(t, 4)
    left, right = pose(LEFT, left, amount), pose(RIGHT, right, amount)
    left, right = (replace(eye, kink=eye.kink * squeeze) for eye in (left, right))
    return Face(left, right, dx=2 * wave(t, 8) * amount,
                dy=-7 * abs(wave(t, 4)) * amount)


def funny(t: float) -> Face:
    amount = envelope(t, 0.2)
    left, right = both(y=EYE_Y - 6, w=64, open=0, bend=-14, tilt=-14)
    tears = clamp(amount * 2 - 1)

    def draw_tears(painter: Painter) -> None:
        for x, side in ((LEFT_X - 30, -1), (RIGHT_X + 30, 1)):
            for offset in (0.0, 0.5):
                u = cycle(t, 3, offset)
                size = 9 * tears * smooth(u / 0.15) * (1 - 0.35 * u)
                drop(painter, x + side * (8 + 26 * u), EYE_Y + 8 - 22 * u + 90 * u * u, size)

    return Face(pose(LEFT, left, amount), pose(RIGHT, right, amount),
                dx=3 * wave(t, 6) * amount, dy=-3 * abs(wave(t, 3)) * amount,
                extras=[draw_tears])


def sad(t: float) -> Face:
    amount = envelope(t, 0.2, 0.18)
    left, right = both(y=EYE_Y + 14, w=70, h=70, lid=0.3, lid_slant=-16)
    sink = 3 * wave(t, 1, 0.75) * amount + 3 * amount
    closed = blink(t, 0.56, 0.12)

    def tear(painter: Painter) -> None:
        u = (t - 0.3) / 0.5
        if 0 < u < 1:
            size = 7 * smooth(u / 0.25) * smooth((1 - u) / 0.15)
            drop(painter, RIGHT_X + 28, EYE_Y + 40 + 44 * u * u, size)

    return Face(shut(pose(LEFT, left, amount), closed),
                shut(pose(RIGHT, right, amount), closed), dy=sink, extras=[tear])


def angry(t: float) -> Face:
    amount = envelope(t, 0.16)
    left, right = both(y=EYE_Y + 6, w=82, h=72, round=0.9, tilt=5,
                       lid=0.42, lid_slant=26)
    throb = 1 + 0.18 * abs(wave(t, 3))
    return Face(pose(LEFT, left, amount), pose(RIGHT, right, amount),
                dx=1.6 * wave(t, 11) * amount,
                extras=[lambda p: anger_mark(p, 204, 52, 15 * amount * throb)])


def crying(t: float) -> Face:
    amount = envelope(t, 0.2)
    left, right = both(y=EYE_Y - 6, w=70, open=0, bend=3, tilt=-14)
    tears = clamp(amount * 2 - 1)

    def draw_tears(painter: Painter) -> None:
        for x in (LEFT_X - 14, RIGHT_X + 14):
            for index in range(4):
                u = cycle(t, 3, index / 4)
                size = 7 * tears * smooth(u / 0.1)
                drop(painter, x, lerp(EYE_Y + 10, SIZE + 20, u), size, 2.6)

    return Face(pose(LEFT, left, amount), pose(RIGHT, right, amount),
                dy=-3 * abs(wave(t, 4)) * amount, extras=[draw_tears])


def loving(t: float) -> Face:
    amount = envelope(t, 0.16, ease=pop)
    left, right = both(y=EYE_Y - 2, w=86, h=80, heart=1)
    beat_phase = cycle(t, 3)
    beat = 0.12 * window(beat_phase, 0.0, 0.22, 0.5) + 0.07 * window(beat_phase, 0.24, 0.44, 0.5)
    left, right = (scaled(pose(base, target, amount), 1 + beat * amount)
                   for base, target in ((LEFT, left), (RIGHT, right)))

    def float_heart(painter: Painter) -> None:
        u = cycle(t, 2)
        heart(painter, 120 + 8 * wave(u, 1), lerp(190, 40, u),
              20 * amount * smooth(u / 0.25) * smooth((1 - u) / 0.3))

    return Face(left, right, dy=-2 * wave(t, 2) * amount, extras=[float_heart])


def embarrassed(t: float) -> Face:
    amount = envelope(t, 0.18)
    dart = -12 - 4 * wave(t, 2) * amount
    left, right = both(y=EYE_Y + 6, w=68, h=64, lid=0.24, lid_slant=-10)
    left, right = (moved(eye, dart * amount, 0) for eye in (left, right))
    closed = max(blink(t, 0.48, 0.07), blink(t, 0.58, 0.07))

    def draw_extras(painter: Painter) -> None:
        blush(painter, LEFT_X - 4, EYE_Y + 52, amount, t)
        blush(painter, RIGHT_X + 4, EYE_Y + 52, amount, t)
        drop(painter, 212, 66 + 16 * cycle(t, 1), 7 * amount, 2.2)

    return Face(shut(pose(LEFT, left, amount), closed),
                shut(pose(RIGHT, right, amount), closed),
                dx=1.2 * wave(t, 9) * amount, extras=[draw_extras])


def surprised(t: float) -> Face:
    amount = envelope(t, 0.14, ease=pop)
    left, right = both(y=EYE_Y - 6, w=64, h=102)
    stretch = 1 + 0.05 * wave(t, 3) * amount
    left, right = (replace(eye, h=eye.h * stretch)
                   for eye in (pose(LEFT, left, amount), pose(RIGHT, right, amount)))
    closed = max(blink(t, 0.58, 0.07), blink(t, 0.68, 0.07))
    burst = clamp(amount)

    def surprise_lines(painter: Painter) -> None:
        if burst < 0.05:
            return
        for eye_x, side in ((LEFT_X, -1), (RIGHT_X, 1)):
            cx, cy = eye_x + side * 30, 62
            for angle in (-40, 0, 40):
                a = math.radians(angle + side * 30)
                inner, outer = 10, 10 + 14 * burst
                painter.stroke([(cx + inner * math.sin(a), cy - inner * math.cos(a)),
                                (cx + outer * math.sin(a), cy - outer * math.cos(a))],
                               5 * burst)

    return Face(shut(left, closed), shut(right, closed),
                dy=-2 * wave(t, 3) * amount, extras=[surprise_lines])


def shocked(t: float) -> Face:
    amount = envelope(t, 0.14, ease=pop)
    jitter = 2.5 * wave(t, 9) * amount
    left, right = both(y=EYE_Y - 4, w=82, h=106, hole=0.64, glint=14)
    left, right = (replace(pose(base, target, amount), glint_x=jitter)
                   for base, target in ((LEFT, left), (RIGHT, right)))

    def gloom(painter: Painter) -> None:
        for index, x in enumerate((100, 120, 140)):
            length = (16 + 5 * wave(t, 4, index / 3)) * amount
            painter.stroke([(x, 14), (x, 14 + length)], 5 * clamp(amount))
        drop(painter, 224, 70 + 20 * cycle(t, 2), 7 * clamp(amount), 2.2)

    return Face(left, right, dx=2.2 * wave(t, 13) * amount, extras=[gloom])


def thinking(t: float) -> Face:
    amount = envelope(t, 0.18)
    drift = 4 * wave(t, 1) * amount
    left = Eye(LEFT_X + 12 + drift, EYE_Y - 10, w=70, h=70, lid=0.32, lid_slant=16)
    right = Eye(RIGHT_X + 12 + drift, EYE_Y - 12, w=72, h=72)

    def dots(painter: Painter) -> None:
        u = cycle(t, 2)
        for index, (x, size) in enumerate(((160, 9), (180, 11), (202, 13))):
            visible = smooth((u - 0.12 - index * 0.16) / 0.08) * smooth((0.92 - u) / 0.08)
            painter.ellipse(x, 42 - index * 4, size * visible * amount, size * visible * amount)

    return Face(pose(LEFT, left, amount), pose(RIGHT, right, amount), extras=[dots])


def winking(t: float) -> Face:
    amount = envelope(t, 0.2)
    left = Eye(LEFT_X, EYE_Y - 2, w=82, h=84)
    right = Eye(RIGHT_X, EYE_Y - 8, w=66, open=0, bend=-12, tilt=-8)
    twinkle = clamp(amount * 2 - 1) * (9 + 3 * abs(wave(t, 3)))
    return Face(pose(LEFT, left, amount), pose(RIGHT, right, amount),
                dy=-2 * abs(wave(t, 2)) * amount,
                extras=[lambda p: sparkle(p, 214, 74, twinkle)])


def cool(t: float) -> Face:
    amount = envelope(t, 0.18)
    left, right = both(spread=-2, y=EYE_Y - 2, w=88, h=54, round=0.42, tilt=-3)
    left, right = pose(LEFT, left, amount), pose(RIGHT, right, amount)
    left = replace(left, shine=(t - 0.42) / 0.2)
    right = replace(right, shine=(t - 0.46) / 0.2)

    def glasses_frame(painter: Painter) -> None:
        width = 7 * amount
        if width < 0.5:
            return
        top = EYE_Y - 2 - 27 * amount + 6
        left_edge, right_edge = left.x - left.w / 2, right.x + right.w / 2
        painter.stroke([(left.x + left.w / 2 - 4, top), (right.x - right.w / 2 + 4, top)], width)
        painter.stroke([(left_edge + 2, top - 2), (left_edge - 12, top - 12)], width * 0.8)
        painter.stroke([(right_edge - 2, top - 2), (right_edge + 12, top - 12)], width * 0.8)

    return Face(left, right, dy=-6 * window(t, 0.72, 0.86), extras=[glasses_frame])


def relaxed(t: float) -> Face:
    amount = envelope(t, 0.2, 0.2)
    left, right = both(y=EYE_Y + 4, w=68, open=0, bend=12)
    breathe = 1 + 0.05 * wave(t, 2) * amount
    left, right = (replace(eye, w=eye.w * breathe)
                   for eye in (pose(LEFT, left, amount), pose(RIGHT, right, amount)))
    return Face(left, right, dx=3 * wave(t, 1) * amount, dy=3 * wave(t, 2, 0.25) * amount)


def delicious(t: float) -> Face:
    amount = envelope(t, 0.18)
    left, right = both(y=EYE_Y - 12, w=80, h=78, cheek=0.52)

    def drool(painter: Painter) -> None:
        u = cycle(t, 2)
        top = 172
        if u < 0.6:
            radius = 7.5 * smooth(u / 0.35) * amount
            hang = top + radius + 12 * smooth((u - 0.3) / 0.3)
            painter.stroke([(150, top), (150, hang - radius)], 4 * amount)
            drop(painter, 150, hang, radius, 1.6)
        else:
            fall = (u - 0.6) / 0.4
            drop(painter, 150, top + 20 + 90 * fall * fall, 7.5 * amount, 2.4)
        sparkle(painter, 204, 56, (8 + 3 * abs(wave(t, 3))) * clamp(amount * 2 - 1))

    return Face(pose(LEFT, left, amount), pose(RIGHT, right, amount),
                dx=3 * wave(t, 2) * amount, extras=[drool])


def kissy(t: float) -> Face:
    amount = envelope(t, 0.2)
    left, right = both(y=EYE_Y - 6, w=62, open=0, bend=-10, tilt=-8)
    hearts = clamp(amount * 2 - 1)

    def flying_hearts(painter: Painter) -> None:
        for offset, size in ((0.0, 26), (0.5, 18)):
            u = cycle(t, 2, offset)
            visible = smooth(u / 0.2) * smooth((1 - u) / 0.25)
            heart(painter, 120 + 10 * wave(u, 1.5), lerp(200, 36, u),
                  size * visible * hearts)

    return Face(pose(LEFT, left, amount), pose(RIGHT, right, amount),
                dy=-2 * wave(t, 2) * amount, extras=[flying_hearts])


def confident(t: float) -> Face:
    amount = envelope(t, 0.18)
    glance = 10 + 4 * wave(t, 1) * amount
    smug = window(t, 0.55, 0.75)
    left = Eye(LEFT_X + glance, EYE_Y + 4, w=78, h=64, lid=0.38 - 0.12 * smug, lid_slant=-6)
    right = Eye(RIGHT_X + glance, EYE_Y + 4, w=78, h=64, lid=0.5, lid_slant=8)
    return Face(pose(LEFT, left, amount), pose(RIGHT, right, amount),
                dy=-3 * smug * amount)


def sleepy(t: float) -> Face:
    amount = envelope(t, 0.3, 0.2)
    droop = smooth(amount / 0.45)
    closing = smooth((amount - 0.45) / 0.35)
    curve = smooth((amount - 0.8) / 0.2)
    left, right = (
        Eye(x, EYE_Y + 12 * droop, w=lerp(EYE_SIZE, 70, droop), h=lerp(EYE_SIZE, 62, droop),
            lid=0.5 * droop, tilt=-4 * droop, open=1 - closing, bend=5 * curve)
        for x in (LEFT_X, RIGHT_X)
    )

    def snore(painter: Painter) -> None:
        for index in range(3):
            u = cycle(t, 2, index / 3)
            visible = smooth(u / 0.15) * smooth((1 - u) / 0.2) * curve
            letter_z(painter, 186 + 30 * u, 92 - 64 * u, (5 + 7 * u) * visible)

    return Face(left, right, dy=3 * wave(t, 2) * curve, extras=[snore])


def silly(t: float) -> Face:
    amount = envelope(t, 0.2)
    left = Eye(LEFT_X - 4, EYE_Y - 4, w=92, h=92, hole=0.34,
               hole_x=12 * math.cos(2 * math.pi * 2 * t),
               hole_y=12 * math.sin(2 * math.pi * 2 * t))
    right = Eye(RIGHT_X + 4, EYE_Y + 2, w=56, open=0, kink=18)
    left, right = pose(LEFT, left, amount), pose(RIGHT, right, amount)
    sway = 5 * wave(t, 2) * amount
    return Face(moved(left, 0, sway), moved(right, 0, -sway))


def confused(t: float) -> Face:
    amount = envelope(t, 0.18)
    look = 6 * wave(t, 1) * amount
    left = Eye(LEFT_X + look, EYE_Y - 6, w=72, h=88)
    right = Eye(RIGHT_X + look, EYE_Y + 8, w=74, h=58, tilt=8, lid=0.34, lid_slant=-16)
    sway = wave(t, 2) * amount
    return Face(pose(LEFT, left, amount), pose(RIGHT, right, amount),
                extras=[lambda p: question_mark(p, 210 + 4 * sway, 34 - 3 * abs(sway),
                                                12 * clamp(amount))])


# Xiaozhi EmojiCollection order; must match src/otto_emoji_gif.c.
EXPRESSIONS: dict[str, tuple[Callable[[float], Face], int]] = {
    "neutral": (neutral, 50),
    "happy": (happy, 40),
    "laughing": (laughing, 40),
    "funny": (funny, 40),
    "sad": (sad, 44),
    "angry": (angry, 40),
    "crying": (crying, 40),
    "loving": (loving, 40),
    "embarrassed": (embarrassed, 44),
    "surprised": (surprised, 40),
    "shocked": (shocked, 40),
    "thinking": (thinking, 44),
    "winking": (winking, 40),
    "cool": (cool, 44),
    "relaxed": (relaxed, 44),
    "delicious": (delicious, 40),
    "kissy": (kissy, 40),
    "confident": (confident, 44),
    "sleepy": (sleepy, 50),
    "silly": (silly, 40),
    "confused": (confused, 40),
}


def render(face: Face) -> Image.Image:
    painter = Painter(face.dx, face.dy)
    draw_eye(painter, face.left, 1)
    draw_eye(painter, face.right, -1)
    for extra in face.extras:
        extra(painter)
    return painter.frame()


def render_frames(name: str) -> list[Image.Image]:
    expression, frame_count = EXPRESSIONS[name]
    return [render(expression(index / frame_count)) for index in range(frame_count)]


def save_gif(name: str) -> Path:
    frames = render_frames(name)
    output_path = OUTPUT_DIR / f"{name}.gif"
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        disposal=1,
        optimize=True,
        palette=GIF_PALETTE,
        transparency=GRAY_LEVELS,
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("names", nargs="*", metavar="name",
                        help="expressions to render (default: all)")
    args = parser.parse_args()
    unknown = sorted(set(args.names) - set(EXPRESSIONS))
    if unknown:
        parser.error(f"unknown expression(s): {', '.join(unknown)}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in args.names or EXPRESSIONS:
        path = save_gif(name)
        print(f"generated {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
