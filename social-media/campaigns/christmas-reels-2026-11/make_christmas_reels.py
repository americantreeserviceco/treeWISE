"""Render two Christmas Instagram Reels (1080x1920, 30 fps, 9-10 s) for American Tree Colorado.

Uses the fictional Santa illustration from social-media/images/seasonal/christmas/ and approved
copy only (brand-guidelines.md section 3). No prices, offers or deadlines.
Frames are drawn with Pillow and piped to ffmpeg. A silent AAC track is added so upload paths
accept the file; add licensed music in Instagram's own library when posting.
Usage: python3 make_christmas_reels.py  -> writes two .mp4 files next to this script.
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SANTA = ROOT / "social-media/images/seasonal/christmas/santa.png"
LOGO = ROOT / "website/assets/images/logo/AmericanTree_Logo_RGB@2x.png"
W, H, FPS = 1080, 1920, 30
AMBER, CREAM, BROWN, FOREST = (245, 166, 35), (253, 248, 238), (59, 42, 32), (30, 74, 46)
BOLD = "/usr/share/fonts/truetype/ibm-plex/IBMPlexSansCondensed-Bold.ttf"
SEMI = "/usr/share/fonts/truetype/ibm-plex/IBMPlexSansCondensed-SemiBold.ttf"

REELS = {
    "reel-1-season-greetings": [
        {"kicker": "SEASON'S GREETINGS", "head": "From our crew\nto yours", "dur": 3.5},
        {"kicker": "COLORADO CHRISTMAS", "head": "Take care of the\ntrees that\nshade your holidays", "dur": 3.0},
    ],
    "reel-2-winter-tree-care": [
        {"kicker": "WINTER TREE CARE", "head": "Feed your trees\nthrough winter", "dur": 3.5},
        {"kicker": "FREE ESTIMATES", "head": "Trimming, pruning\nand stump grinding", "dur": 2.5},
    ],
}
END_LINE = "Request a free estimate"
END_DUR = 2.5


def font(path, size):
    return ImageFont.truetype(path, size)


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def background():
    """Forest-to-brown vertical gradient with a soft vignette."""
    top, bottom = FOREST, BROWN
    bg = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    return bg


def text_block(canvas, kicker, head, t, y0=1200):
    a = ease((t - 0.1) / 0.6)
    if a <= 0:
        return
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    kf, hf = font(SEMI, 42), font(BOLD, 84)
    y = y0 + int((1 - a) * 40)
    kw = d.textlength(kicker, font=kf)
    d.text(((W - kw) / 2, y), kicker, font=kf, fill=AMBER + (255,))
    y += 74
    for line in head.split("\n"):
        lw = d.textlength(line, font=hf)
        d.text(((W - lw) / 2 + 3, y + 4), line, font=hf, fill=(0, 0, 0, 170))
        d.text(((W - lw) / 2, y), line, font=hf, fill=CREAM + (255,))
        y += 96
    if a < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    canvas.alpha_composite(layer)


class SantaScene:
    def __init__(self, spec):
        self.spec, self.dur = spec, spec["dur"]
        self.base = background()
        santa = Image.open(SANTA).convert("RGBA")
        sw = 760
        self.santa = santa.resize((sw, round(santa.height * sw / santa.width)), Image.LANCZOS)

    def frame(self, t):
        f = self.base.copy()
        # Gentle bob, so the illustration moves without changing its size.
        bob = int(12 * (1 - abs(2 * ((t * 0.8) % 1) - 1)))
        s = self.santa
        f.alpha_composite(s, ((W - s.width) // 2, 150 + bob))
        text_block(f, self.spec["kicker"], self.spec["head"], t)
        return f


class EndScene:
    dur = END_DUR

    def __init__(self):
        logo = Image.open(LOGO).convert("RGBA")
        lw = 700
        self.logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
        self.bg = background()

    def frame(self, t):
        f = self.bg.copy()
        d = ImageDraw.Draw(f)
        a = ease(t / 0.6)
        logo = self.logo.copy()
        logo.putalpha(logo.getchannel("A").point(lambda v: int(v * a)))
        f.alpha_composite(logo, ((W - logo.width) // 2, 640 + int((1 - a) * 30)))
        cf, sf = font(BOLD, 62), font(SEMI, 44)
        for text, fnt, y, fill, at in (
            (END_LINE, cf, 1120, CREAM, 0.5),
            ("americantreeserviceco.com", sf, 1230, AMBER, 0.8),
        ):
            k = ease((t - at) / 0.5)
            w = d.textlength(text, font=fnt)
            d.text(((W - w) / 2, y + int((1 - k) * 30)), text, font=fnt, fill=fill + (int(255 * k),))
        return f


def render(name, scenes_spec):
    scenes = [SantaScene(s) for s in scenes_spec] + [EndScene()]
    out = HERE / f"{name}.mp4"
    total = sum(s.dur for s in scenes)
    proc = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", f"{total:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out),
    ], stdin=subprocess.PIPE)
    for scene in scenes:
        for i in range(int(round(scene.dur * FPS))):
            proc.stdin.write(scene.frame(i / FPS).convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit(f"ffmpeg failed for {name}")
    print(f"{out.name}: {total:.1f} s")


if __name__ == "__main__":
    for reel_name, spec in REELS.items():
        render(reel_name, spec)
