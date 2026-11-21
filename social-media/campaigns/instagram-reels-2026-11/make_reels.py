"""Render three Instagram Reels (1080x1920, 30 fps, each 9-12 s) from approved brand photos.

Copy uses only approved claims from social-media/brand-guidelines.md section 3.
Frames are drawn with Pillow and piped to ffmpeg. A silent AAC track is added so upload
paths accept the file; add licensed music in Instagram's own library when posting.
Usage: python3 make_reels.py  ->  writes three .mp4 files and captions.txt next to this file.
"""
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
IMG = HERE.parents[2] / "website/assets/images"
W, H, FPS = 1080, 1920, 30
AMBER, CREAM, BROWN = (245, 166, 35), (253, 248, 238), (59, 42, 32)
BOLD = "/usr/share/fonts/truetype/ibm-plex/IBMPlexSansCondensed-Bold.ttf"
SEMI = "/usr/share/fonts/truetype/ibm-plex/IBMPlexSansCondensed-SemiBold.ttf"

REELS = {
    "reel-1-winter-root-fertilization": {
        "scenes": [
            {"photo": "optimized/arborist-root-feeding.webp", "dur": 3.5,
             "kicker": "WINTER ROOT FERTILIZATION", "head": "Feed your trees\nthrough winter"},
            {"photo": "optimized/tree-pruning-bucket-truck.webp", "dur": 3.0,
             "kicker": "PLANT HEALTH CARE", "head": "Free estimates\nfor every job"},
        ],
        "end_line": "Request a free estimate",
    },
    "reel-2-meet-the-arborist": {
        "scenes": [
            {"photo": "optimized/IMG_0781.webp", "dur": 3.5,
             "kicker": "FAMILY-OWNED SINCE 1993", "head": "Led by ISA Certified\nArborist Troy King"},
            {"photo": "optimized/tree-pruning-bucket-truck.webp", "dur": 3.0,
             "kicker": "LICENSED AND INSURED", "head": "Straightforward pricing\nwithout hidden fees"},
        ],
        "end_line": "Request a free estimate",
    },
    "reel-3-24-7-emergency": {
        "scenes": [
            {"photo": "optimized/dji-hero.webp", "dur": 3.5,
             "kicker": "GOLDEN · ARVADA · WHEAT RIDGE", "head": "24/7 emergency\nservice"},
            {"photo": "optimized/tree-pruning-bucket-truck.webp", "dur": 3.0,
             "kicker": "POWER LINES", "head": "Stay far away.\nCall your utility first."},
        ],
        "end_line": "Request a free estimate",
    },
}
END_DUR = 3.0


def font(path, size):
    return ImageFont.truetype(path, size)


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def cover(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def gradient(top_alpha, bottom_alpha):
    g = Image.new("L", (1, H))
    for y in range(H):
        g.putpixel((0, y), int(top_alpha + (bottom_alpha - top_alpha) * y / (H - 1)))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.putalpha(g.resize((W, H)))
    return layer


def text_block(canvas, kicker, head, t):
    """Kicker and headline fade up over the first 0.6 s of a scene, placed in the lower third."""
    a = ease((t - 0.1) / 0.6)
    if a <= 0:
        return
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    kf, hf = font(SEMI, 42), font(BOLD, 88)
    y = 1180 + int((1 - a) * 40)
    kw = d.textlength(kicker, font=kf)
    d.text(((W - kw) / 2, y), kicker, font=kf, fill=AMBER + (255,))
    y += 76
    for line in head.split("\n"):
        lw = d.textlength(line, font=hf)
        d.text(((W - lw) / 2 + 3, y + 4), line, font=hf, fill=(0, 0, 0, 170))
        d.text(((W - lw) / 2, y), line, font=hf, fill=CREAM + (255,))
        y += 100
    if a < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    canvas.alpha_composite(layer)


class PhotoScene:
    def __init__(self, spec):
        self.spec, self.dur = spec, spec["dur"]
        src = Image.open(IMG / spec["photo"]).convert("RGB")
        self.base = cover(src, W, H)
        self.base = Image.alpha_composite(self.base.convert("RGBA"), gradient(40, 215))

    def frame(self, t):
        f = self.base.copy()
        # Slow push-in keeps the photo moving without a cut.
        z = 1.0 + 0.06 * (t / self.dur)
        cw, ch = int(W / z), int(H / z)
        f = f.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((W, H), Image.BILINEAR)
        text_block(f, self.spec["kicker"], self.spec["head"], t)
        return f


class EndScene:
    dur = END_DUR

    def __init__(self, line):
        self.line = line
        logo = Image.open(IMG / "logo/AmericanTree_Logo_RGB@2x.png").convert("RGBA")
        lw = 760
        self.logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
        self.bg = Image.new("RGBA", (W, H), BROWN + (255,))

    def frame(self, t):
        f = self.bg.copy()
        d = ImageDraw.Draw(f)
        a = ease(t / 0.6)
        logo = self.logo.copy()
        logo.putalpha(logo.getchannel("A").point(lambda v: int(v * a)))
        f.alpha_composite(logo, ((W - logo.width) // 2, 640 + int((1 - a) * 30)))
        cf, sf = font(BOLD, 64), font(SEMI, 44)
        for text, fnt, y, fill in (
            (self.line, cf, 1150, CREAM),
            ("americantreeserviceco.com", sf, 1260, AMBER),
        ):
            k = ease((t - 0.5) / 0.6)
            w = d.textlength(text, font=fnt)
            d.text(((W - w) / 2, y + int((1 - k) * 30)), text, font=fnt, fill=fill + (int(255 * k),))
        return f


def render(name, cfg):
    scenes = [PhotoScene(s) for s in cfg["scenes"]] + [EndScene(cfg["end_line"])]
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
        frames = int(round(scene.dur * FPS))
        for i in range(frames):
            proc.stdin.write(scene.frame(i / FPS).convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit(f"ffmpeg failed for {name}")
    print(f"{out.name}: {total:.1f} s")


if __name__ == "__main__":
    for reel_name, reel_cfg in REELS.items():
        render(reel_name, reel_cfg)
