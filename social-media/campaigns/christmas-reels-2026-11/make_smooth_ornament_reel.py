"""Render the smooth 12 Days ornament Reel: same frames as make_ornament_reel.py, but each ornament holds longer and
dissolves into the next one. Includes Day 5 (the gold rings ornament). 1080x1920, 30 fps.
Usage: python3 make_smooth_ornament_reel.py -> writes reel-4-twelve-days-ornaments-smooth.mp4 next to this script.
"""
import subprocess

from PIL import Image

import make_ornament_reel as base_reel
from make_ornament_reel import DAYS, FPS, H, HERE, LOGO, W, background, end_frame, ornament_frame, title_frame

HOLD, FADE = 1.4, 0.4        # seconds each ornament is on screen, and the dissolve into the next
TITLE, END = 2.5, 3.0


def main():
    bg = background()
    ornaments = {d: Image.open(HERE / "ornaments" / f"day-{d:02d}.webp").convert("RGBA") for d in DAYS}
    logo = Image.open(LOGO).convert("RGBA")
    logo = logo.resize((700, round(logo.height * 700 / logo.width)), Image.LANCZOS)

    base_reel.ORNAMENT_DUR = HOLD   # the grow-in animation is timed from this
    total = TITLE + HOLD * len(DAYS) + END
    out = HERE / "reel-4-twelve-days-ornaments-smooth.mp4"
    proc = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", f"{total:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
    ], stdin=subprocess.PIPE)

    def put(img):
        proc.stdin.write(img.convert("RGB").tobytes())

    for i in range(int(TITLE * FPS)):
        put(title_frame(bg, i / FPS))
    for n, day in enumerate(DAYS):
        nxt = DAYS[n + 1] if n + 1 < len(DAYS) else None
        for i in range(int(HOLD * FPS)):
            t = i / FPS
            frame = ornament_frame(bg, ornaments[day], day, t)
            fade_start = HOLD - FADE
            if nxt is not None and t >= fade_start:
                # Dissolve into the first moments of the next ornament.
                k = (t - fade_start) / FADE
                frame = Image.blend(frame.convert("RGB"), ornament_frame(bg, ornaments[nxt], nxt, t - fade_start).convert("RGB"), k)
            put(frame)
    for i in range(int(END * FPS)):
        put(end_frame(bg, logo, i / FPS))
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg failed")
    print(f"{out.name}: {total:.1f} s")


if __name__ == "__main__":
    main()
