"""Render a prize-free spin reel (1080x1920, 30 fps, 10 s) for American Tree Colorado.

A festive wheel spins and slows, then lands on a "Day 12" segment. It has no prizes, offers,
discounts or claim text, per brand-guidelines.md section 3. Segment labels are only day numbers.
Usage: python3 make_spin_reel.py  -> writes reel-3-spin-the-wheel.mp4 next to this script.
"""
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOGO = ROOT / "website/assets/images/logo/AmericanTree_Logo_RGB@2x.png"
W, H, FPS = 1080, 1920, 30
AMBER, CREAM, BROWN, FOREST, RUST, LEAF = (245, 166, 35), (253, 248, 238), (59, 42, 32), (30, 74, 46), (165, 79, 37), (62, 128, 70)
BOLD = "/usr/share/fonts/truetype/ibm-plex/IBMPlexSansCondensed-Bold.ttf"
SEMI = "/usr/share/fonts/truetype/ibm-plex/IBMPlexSansCondensed-SemiBold.ttf"

SPIN_DUR, HOLD_DUR, END_DUR = 6.0, 2.5, 2.0
SEGMENTS = 12
COLOURS = [RUST, FOREST, AMBER, LEAF]
WHEEL_R, WHEEL_CX, WHEEL_CY = 420, W // 2, 920
END_LINE = "Request a free estimate"
TOTAL_TURNS = 7.25  # full turns plus a fraction so the wheel stops mid-segment, not on a line


def font(path, size):
    return ImageFont.truetype(path, size)


def ease_out(t):
    return 1 - (1 - max(0.0, min(1.0, t))) ** 3


def background():
    bg = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(FOREST[i] + (BROWN[i] - FOREST[i]) * t) for i in range(3)) + (255,))
    return bg


def wheel_layer(angle_deg):
    size = WHEEL_R * 2 + 40
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = size // 2
    seg = 360 / SEGMENTS
    lf = font(BOLD, 64)
    for i in range(SEGMENTS):
        start = angle_deg + i * seg
        d.pieslice((c - WHEEL_R, c - WHEEL_R, c + WHEEL_R, c + WHEEL_R), start, start + seg,
                   fill=COLOURS[i % len(COLOURS)] + (255,), outline=CREAM + (255,), width=6)
        mid = math.radians(start + seg / 2)
        tx, ty = c + math.cos(mid) * WHEEL_R * 0.68, c + math.sin(mid) * WHEEL_R * 0.68
        label = str(i + 1)
        lw = d.textlength(label, font=lf)
        d.text((tx - lw / 2, ty - 40), label, font=lf, fill=CREAM + (255,))
    d.ellipse((c - 70, c - 70, c + 70, c + 70), fill=BROWN + (255,), outline=AMBER + (255,), width=8)
    return layer


def pointer(canvas):
    d = ImageDraw.Draw(canvas)
    top = WHEEL_CY - WHEEL_R - 40
    d.polygon([(W // 2 - 40, top - 70), (W // 2 + 40, top - 70), (W // 2, top + 20)], fill=AMBER + (255,),
              outline=CREAM + (255,))


def text_centred(canvas, text, fnt, y, fill, alpha=1.0):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w = d.textlength(text, font=fnt)
    d.text(((W - w) / 2 + 3, y + 4), text, font=fnt, fill=(0, 0, 0, 170))
    d.text(((W - w) / 2, y), text, font=fnt, fill=fill + (255,))
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * max(0.0, alpha))))
    canvas.alpha_composite(layer)


def frame_spin(t, base):
    f = base.copy()
    progress = min(1.0, t / SPIN_DUR)
    angle = -90 + 360 * TOTAL_TURNS * ease_out(progress)
    wheel = wheel_layer(angle).rotate(0)
    f.alpha_composite(wheel, (WHEEL_CX - wheel.width // 2, WHEEL_CY - wheel.height // 2))
    pointer(f)
    text_centred(f, "SPIN THE WHEEL", font(SEMI, 46), 190, AMBER)
    text_centred(f, "12 days of holiday cheer", font(BOLD, 74), 250, CREAM)
    return f


def frame_hold(t, base):
    f = frame_spin(SPIN_DUR, base)
    a = ease_out(t / 0.5)
    text_centred(f, "Season's greetings", font(BOLD, 70), 1380, CREAM, a)
    text_centred(f, "from our crew", font(SEMI, 48), 1470, AMBER, a)
    return f


def frame_end(t, base, logo):
    f = base.copy()
    a = ease_out(t / 0.6)
    lg = logo.copy()
    lg.putalpha(lg.getchannel("A").point(lambda v: int(v * a)))
    f.alpha_composite(lg, ((W - lg.width) // 2, 640 + int((1 - a) * 30)))
    text_centred(f, END_LINE, font(BOLD, 62), 1120, CREAM, ease_out((t - 0.5) / 0.5))
    text_centred(f, "americantreeserviceco.com", font(SEMI, 44), 1230, AMBER, ease_out((t - 0.8) / 0.5))
    return f


def main():
    base = background()
    logo = Image.open(LOGO).convert("RGBA")
    lw = 700
    logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
    out = HERE / "reel-3-spin-the-wheel.mp4"
    total = SPIN_DUR + HOLD_DUR + END_DUR
    proc = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", f"{total:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
    ], stdin=subprocess.PIPE)
    for i in range(int(SPIN_DUR * FPS)):
        proc.stdin.write(frame_spin(i / FPS, base).convert("RGB").tobytes())
    for i in range(int(HOLD_DUR * FPS)):
        proc.stdin.write(frame_hold(i / FPS, base).convert("RGB").tobytes())
    for i in range(int(END_DUR * FPS)):
        proc.stdin.write(frame_end(i / FPS, base, logo).convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed")
    print(f"{out.name}: {total:.1f} s")


if __name__ == "__main__":
    main()
