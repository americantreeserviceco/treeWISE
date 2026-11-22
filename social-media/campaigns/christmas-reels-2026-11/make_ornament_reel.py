"""Render the 12 Days ornament Reel (1080x1920, 30 fps, about 13 s) for American Tree Colorado.

Shows the day ornaments in order from ornaments/day-NN.webp. Each ornament holds for a moment with
its day number. The gift and prize-wheel
ornaments are left out because they read as prizes, and the Olympic-rings ornament is left out
because the rings are a protected emblem. No prices, offers or claims.
Usage: python3 make_ornament_reel.py  -> writes reel-4-twelve-days-ornaments.mp4 next to this script.
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOGO = ROOT / "website/assets/images/logo/AmericanTree_Logo_RGB@2x.png"
W, H, FPS = 1080, 1920, 30
AMBER, CREAM, BROWN, FOREST = (245, 166, 35), (253, 248, 238), (59, 42, 32), (30, 74, 46)
BOLD = "/usr/share/fonts/truetype/ibm-plex/IBMPlexSansCondensed-Bold.ttf"
SEMI = "/usr/share/fonts/truetype/ibm-plex/IBMPlexSansCondensed-SemiBold.ttf"

ORNAMENT_DUR = 0.75
TITLE_DUR, END_DUR = 2.0, 2.5
END_LINE = "Request a free estimate"
DAYS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]


def font(path, size):
    return ImageFont.truetype(path, size)


def ease(t):
    return 1 - (1 - max(0.0, min(1.0, t))) ** 3


def background():
    bg = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(FOREST[i] + (BROWN[i] - FOREST[i]) * t) for i in range(3)) + (255,))
    return bg


def centred(canvas, text, fnt, y, fill, alpha=1.0):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w = d.textlength(text, font=fnt)
    d.text(((W - w) / 2 + 3, y + 4), text, font=fnt, fill=(0, 0, 0, 170))
    d.text(((W - w) / 2, y), text, font=fnt, fill=fill + (255,))
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * max(0.0, alpha))))
    canvas.alpha_composite(layer)


def title_frame(base, t):
    f = base.copy()
    a = ease(t / 0.6)
    centred(f, "12 DAYS OF", font(SEMI, 56), 640, AMBER, a)
    centred(f, "HOLIDAY CHEER", font(BOLD, 110), 720, CREAM, a)
    centred(f, "Season's greetings from our crew", font(SEMI, 46), 880, CREAM, ease((t - 0.6) / 0.6))
    return f


def ornament_frame(base, ornament, day, t):
    f = base.copy()
    # Ornament grows in during the first third of the hold, then holds still.
    s = 0.85 + 0.15 * ease(t / (ORNAMENT_DUR * 0.4))
    size = int(860 * s)
    img = ornament.resize((size, round(ornament.height * size / ornament.width)), Image.LANCZOS)
    f.alpha_composite(img, ((W - img.width) // 2, 560 + (860 - img.height) // 2))
    centred(f, f"DAY {day}", font(BOLD, 96), 1480, AMBER, ease(t / 0.3))
    return f


def end_frame(base, logo, t):
    f = base.copy()
    a = ease(t / 0.6)
    lg = logo.copy()
    lg.putalpha(lg.getchannel("A").point(lambda v: int(v * a)))
    f.alpha_composite(lg, ((W - lg.width) // 2, 640 + int((1 - a) * 30)))
    centred(f, END_LINE, font(BOLD, 62), 1120, CREAM, ease((t - 0.5) / 0.5))
    # Instagram does not make links inside a video clickable, so the address is shown as text.
    centred(f, "americantreeserviceco.com/christmas", font(SEMI, 44), 1230, AMBER, ease((t - 0.8) / 0.5))
    return f


def main():
    base = background()
    ornaments = {d: Image.open(HERE / "ornaments" / f"day-{d:02d}.webp").convert("RGBA") for d in DAYS}
    logo = Image.open(LOGO).convert("RGBA")
    lw = 700
    logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)

    total = TITLE_DUR + ORNAMENT_DUR * len(DAYS) + END_DUR
    out = HERE / "reel-4-twelve-days-ornaments.mp4"
    proc = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", f"{total:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
    ], stdin=subprocess.PIPE)

    for i in range(int(TITLE_DUR * FPS)):
        proc.stdin.write(title_frame(base, i / FPS).convert("RGB").tobytes())
    for day in DAYS:
        for i in range(int(ORNAMENT_DUR * FPS)):
            proc.stdin.write(ornament_frame(base, ornaments[day], day, i / FPS).convert("RGB").tobytes())
    for i in range(int(END_DUR * FPS)):
        proc.stdin.write(end_frame(base, logo, i / FPS).convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed")
    print(f"{out.name}: {total:.1f} s")


if __name__ == "__main__":
    main()
