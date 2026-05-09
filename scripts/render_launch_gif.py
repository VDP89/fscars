"""Render the Functional Scars launch animation to GIF.

Storyboard (4.5 s loop, 30 fps -> 135 frames):

    0.0 - 0.4 s  scar line fades in
    0.4 - 1.4 s  four stitches pop in, one every 0.25 s
    1.4 - 1.9 s  hold the closed wound
    1.9 - 2.4 s  navy rounded square scales in around the wound
    2.4 - 2.9 s  monogram 'fs' fades in inside the square
    2.9 - 3.3 s  square slides left + wordmark 'Functional Scars' slides in from the right
    3.3 - 4.5 s  hold the full logo

Two outputs:
    assets/fscars-launch.gif       (light cream bg)
    assets/fscars-launch-dark.gif  (dark navy bg)

Run:
    python scripts/render_launch_gif.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import NamedTuple

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Brand tokens (must match BRAND.md and assets/fscars-logo.svg)
# ---------------------------------------------------------------------------

NAVY = (15, 26, 46)
CREAM = (245, 241, 232)
TERRACOTA = (204, 120, 92)
SLATE = (71, 85, 105)
SLATE_LIGHT = (148, 163, 184)

# ---------------------------------------------------------------------------
# Output settings
# ---------------------------------------------------------------------------

FPS = 30
DURATION_S = 4.5
N_FRAMES = int(FPS * DURATION_S)
WIDTH = 600
HEIGHT = 360

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


class Theme(NamedTuple):
    name: str
    bg: tuple[int, int, int]
    glyph_bg: tuple[int, int, int]
    glyph_fg: tuple[int, int, int]
    wordmark_color: tuple[int, int, int]


THEME_LIGHT = Theme("light", CREAM, NAVY, CREAM, NAVY)
THEME_DARK = Theme("dark", NAVY, CREAM, NAVY, CREAM)

# ---------------------------------------------------------------------------
# Geometry — the FINAL position of the logo (last frame)
# ---------------------------------------------------------------------------

# The icon (rounded square + monogram + scar line with stitches)
ICON_FINAL_CX = 200
ICON_CY = 180
ICON_SIDE = 120
ICON_RADIUS = 18

# The scar line lives slightly below the monogram inside the icon
SCAR_HALF_WIDTH = 38
SCAR_LINE_WIDTH = 6
STITCH_LINE_WIDTH = 4
STITCH_HALF_HEIGHT = 7
N_STITCHES = 4

# The wordmark
WORDMARK_X = 282
WORDMARK_Y = 165
TAGLINE_Y = 220

# When the wound is "free-floating" (before the icon appears) it sits centered
SCAR_INTRO_CX = WIDTH // 2
SCAR_INTRO_CY = HEIGHT // 2 - 10

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

MONO_FONT_CANDIDATES = [
    # Linux (CI runner, after `apt-get install fonts-jetbrains-mono`)
    "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
    "/usr/share/fonts/TTF/JetBrainsMono-Bold.ttf",
    # Windows
    "C:/Windows/Fonts/consolab.ttf",
    "C:/Windows/Fonts/courbd.ttf",
    # macOS fallback
    "/System/Library/Fonts/Menlo.ttc",
    # Linux fallback
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
]

SANS_REGULAR_CANDIDATES = [
    "C:/Windows/Fonts/Inter-Regular-slnt=0.ttf",
    "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _first_existing(candidates: list[str]) -> str | None:
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def _load_font(candidates: list[str], size: int) -> ImageFont.ImageFont:
    path = _first_existing(candidates)
    if path is None:
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(path, size)
    except (OSError, ValueError):
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Easing
# ---------------------------------------------------------------------------


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def ease_in_out(t: float) -> float:
    """Smooth S-curve easing on [0, 1]."""
    t = clamp(t)
    return (1 - math.cos(math.pi * t)) / 2


def ease_out(t: float) -> float:
    """Decelerating ease on [0, 1]."""
    t = clamp(t)
    return 1 - (1 - t) ** 3


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


def blend(base: tuple[int, int, int], over: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    """Linear blend of `over` onto `base` with alpha in [0, 1]."""
    a = clamp(alpha)
    return tuple(int(round(base[i] + (over[i] - base[i]) * a)) for i in range(3))


def draw_round_line(
    draw: ImageDraw.ImageDraw,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    width: int,
    color: tuple[int, int, int],
) -> None:
    """Line with rounded caps via two filled circles at the endpoints."""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    r = width / 2
    draw.ellipse([(x1 - r, y1 - r), (x1 + r, y1 + r)], fill=color)
    draw.ellipse([(x2 - r, y2 - r), (x2 + r, y2 + r)], fill=color)


def draw_text_centered(
    img: Image.Image,
    text: str,
    *,
    cx: float,
    cy: float,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    """Pillow's anchor='mm' is precise enough for our needs."""
    draw = ImageDraw.Draw(img)
    draw.text((cx, cy), text, font=font, fill=fill, anchor="mm")


def draw_text_left(
    img: Image.Image,
    text: str,
    *,
    x: float,
    y: float,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    draw = ImageDraw.Draw(img)
    draw.text((x, y), text, font=font, fill=fill, anchor="lm")


# ---------------------------------------------------------------------------
# Frame composition
# ---------------------------------------------------------------------------


def render_frame(t: float, theme: Theme, fonts: dict) -> Image.Image:
    """t in [0, 1] across the whole timeline."""
    img = Image.new("RGB", (WIDTH, HEIGHT), theme.bg)
    draw = ImageDraw.Draw(img)

    # Timeline phases in normalized [0, 1]
    p1_line_in = (0.00, 0.09)
    p2_stitches = (0.09, 0.31)        # 4 stitches across this window
    p3_hold_wound = (0.31, 0.42)
    p4_square_in = (0.42, 0.53)
    p5_monogram = (0.53, 0.64)
    p6_slide = (0.64, 0.74)
    p7_hold_logo = (0.74, 1.00)

    # ------- Compute icon transform (slides from center to its final left position) -------
    if t >= p6_slide[0]:
        s = clamp((t - p6_slide[0]) / (p6_slide[1] - p6_slide[0]))
        icon_cx = lerp(WIDTH // 2, ICON_FINAL_CX, ease_in_out(s))
        wordmark_alpha = ease_out(s)
    else:
        icon_cx = WIDTH // 2
        wordmark_alpha = 0.0

    # The scar/icon vertical position holds at HEIGHT/2 until the icon appears
    if t < p4_square_in[0]:
        focus_cy = SCAR_INTRO_CY
    else:
        s = clamp((t - p4_square_in[0]) / (p7_hold_logo[0] - p4_square_in[0]))
        focus_cy = lerp(SCAR_INTRO_CY, ICON_CY, ease_in_out(s))

    # Inside the icon, the scar is always 38px below the monogram center
    scar_cy = focus_cy + 38

    # ------- Phase 4: navy rounded square scales in around the wound -------
    square_progress = 0.0
    if t >= p4_square_in[0]:
        square_progress = clamp((t - p4_square_in[0]) / (p4_square_in[1] - p4_square_in[0]))
    if square_progress > 0:
        s = ease_out(square_progress)
        side = ICON_SIDE * s
        radius = ICON_RADIUS * s
        x0 = icon_cx - side / 2
        y0 = focus_cy - side / 2
        x1 = icon_cx + side / 2
        y1 = focus_cy + side / 2
        if side > 4:
            draw.rounded_rectangle(
                [(x0, y0), (x1, y1)],
                radius=radius,
                fill=theme.glyph_bg,
            )

    # ------- Phase 5: monogram 'fs' fades in inside the square -------
    if t >= p5_monogram[0]:
        s = clamp((t - p5_monogram[0]) / (p5_monogram[1] - p5_monogram[0]))
        a = ease_out(s)
        glyph_color = blend(theme.glyph_bg, theme.glyph_fg, a)
        draw_text_centered(
            img,
            "fs",
            cx=icon_cx,
            cy=focus_cy - 6,
            font=fonts["mono_glyph"],
            fill=glyph_color,
        )

    # ------- Phase 1: the scar line itself (always visible after p1) -------
    if t >= p1_line_in[0]:
        s_line = clamp((t - p1_line_in[0]) / (p1_line_in[1] - p1_line_in[0]))
        a = ease_out(s_line)
        line_color = blend(theme.bg, TERRACOTA, a)
        # The line is drawn ABOVE the square, so it visually sits on top of the
        # rounded rect once that appears.
        draw_round_line(
            draw,
            icon_cx - SCAR_HALF_WIDTH,
            scar_cy,
            icon_cx + SCAR_HALF_WIDTH,
            scar_cy,
            width=SCAR_LINE_WIDTH,
            color=line_color,
        )

    # ------- Phase 2: stitches appear one by one -------
    if t >= p2_stitches[0]:
        s_stitches = clamp((t - p2_stitches[0]) / (p2_stitches[1] - p2_stitches[0]))
        # Each stitch claims 1/N_STITCHES of the phase; pop with quick ease-out.
        for i in range(N_STITCHES):
            stitch_t = clamp(s_stitches * N_STITCHES - i)
            if stitch_t <= 0:
                continue
            a = ease_out(stitch_t)
            color = blend(theme.bg, TERRACOTA, a)
            # Stitches spread evenly across the line width. Width = 76px.
            # Place them at fractions 0.18, 0.39, 0.61, 0.82 so they don't touch the edges.
            fractions = [0.18, 0.39, 0.61, 0.82]
            stitch_x = icon_cx - SCAR_HALF_WIDTH + 2 * SCAR_HALF_WIDTH * fractions[i]
            half_h = STITCH_HALF_HEIGHT * a  # also scales up vertically
            draw_round_line(
                draw,
                stitch_x,
                scar_cy - half_h,
                stitch_x,
                scar_cy + half_h,
                width=STITCH_LINE_WIDTH,
                color=color,
            )

    # ------- Phase 6/7: wordmark "Functional Scars" + tagline -------
    if wordmark_alpha > 0:
        # Color blends from bg (invisible) to wordmark color.
        wm_color = blend(theme.bg, theme.wordmark_color, wordmark_alpha)
        tagline_color = blend(
            theme.bg,
            SLATE_LIGHT if theme.name == "dark" else SLATE,
            wordmark_alpha,
        )
        # Slide-in from the right as it fades in.
        slide_offset = (1.0 - wordmark_alpha) * 30
        draw_text_left(
            img,
            "Functional Scars",
            x=WORDMARK_X + slide_offset,
            y=WORDMARK_Y,
            font=fonts["mono_word"],
            fill=wm_color,
        )
        draw_text_left(
            img,
            "Bolt-on correction primitive",
            x=WORDMARK_X + slide_offset,
            y=TAGLINE_Y,
            font=fonts["sans_tagline"],
            fill=tagline_color,
        )
        draw_text_left(
            img,
            "for AI coding agents",
            x=WORDMARK_X + slide_offset,
            y=TAGLINE_Y + 22,
            font=fonts["sans_tagline"],
            fill=tagline_color,
        )

    return img


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def render_gif(theme: Theme, output_path: Path) -> None:
    fonts = {
        "mono_glyph": _load_font(MONO_FONT_CANDIDATES, 60),
        "mono_word": _load_font(MONO_FONT_CANDIDATES, 28),
        "sans_tagline": _load_font(SANS_REGULAR_CANDIDATES, 16),
    }

    frames: list[Image.Image] = []
    for i in range(N_FRAMES):
        t = i / (N_FRAMES - 1) if N_FRAMES > 1 else 0.0
        frames.append(render_frame(t, theme, fonts))

    # Quantize to 256 colors so the GIF stays small
    palette_frames = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=128) for f in frames]
    duration_ms = int(1000 / FPS)

    palette_frames[0].save(
        output_path,
        save_all=True,
        append_images=palette_frames[1:],
        duration=duration_ms,
        loop=0,             # infinite loop
        optimize=True,
        disposal=2,         # restore to bg between frames (cleaner)
    )
    print(f"  -> {output_path.relative_to(output_path.parent.parent)} ({output_path.stat().st_size // 1024} KB, {len(frames)} frames)")


def main() -> int:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Rendering Functional Scars launch animation ({DURATION_S}s, {FPS}fps, {N_FRAMES} frames)...")
    render_gif(THEME_LIGHT, ASSETS_DIR / "fscars-launch.gif")
    render_gif(THEME_DARK, ASSETS_DIR / "fscars-launch-dark.gif")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
