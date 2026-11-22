"""Draw the Day 5 "five golden rings" ornament (ornaments/day-05-drawn-draft.webp) to match the other day ornaments.

Five separate gold bands sit in a loose arc on a pine bough inside a glass bauble. They never touch or interlock and
are all one colour, so the picture does not echo the Olympic emblem (five interlocked rings in a 3 + 2 pattern).
Usage: python3 make_gold_rings_ornament.py -> writes ornaments/day-05-drawn-draft.webp next to this script.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
S = 4                                  # supersample factor
W, H = 300 * S, 354 * S
CX, CY, R = W // 2, 215 * S, 136 * S   # bauble centre and radius


def grad(size, stops, angle_deg=90):
    """Linear gradient image; stops = [(pos 0..1, (r,g,b))]."""
    w, h = size
    a = math.radians(angle_deg)
    yy, xx = np.mgrid[0:h, 0:w]
    t = ((xx - w / 2) * math.cos(a) + (yy - h / 2) * math.sin(a)) / (abs(w * math.cos(a)) + abs(h * math.sin(a)) + 1e-9) + 0.5
    t = np.clip(t, 0, 1)
    pos = [p for p, _ in stops]
    out = np.stack([np.interp(t, pos, [c[i] for _, c in stops]) for i in range(3)], -1)
    return Image.fromarray(out.astype("uint8"), "RGB")


def mask_circle(cx, cy, r, size):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    return m


def ring(diam, tilt):
    """One upright gold band as an RGBA tile, drawn as a thick ellipse with a gradient and a highlight."""
    w = h = diam
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rx, ry = w * 0.46, h * 0.46
    thick = w * 0.17
    outer = Image.new("L", (w, h), 0)
    ImageDraw.Draw(outer).ellipse([w / 2 - rx, h / 2 - ry, w / 2 + rx, h / 2 + ry], fill=255)
    inner = Image.new("L", (w, h), 0)
    ImageDraw.Draw(inner).ellipse([w / 2 - rx + thick, h / 2 - ry + thick, w / 2 + rx - thick, h / 2 + ry - thick], fill=255)
    band = ImageChops.subtract(outer, inner)
    gold = grad((w, h), [(0, (255, 232, 140)), (0.35, (236, 178, 48)), (0.7, (176, 112, 22)), (1, (120, 70, 14))], 60)
    base.paste(gold, (0, 0), band)
    # Darker inner wall on the lower right, so it reads as a band with depth.
    shade = Image.new("L", (w, h), 0)
    ImageDraw.Draw(shade).ellipse([w / 2 - rx + thick * 0.7, h / 2 - ry + thick * 0.7, w / 2 + rx - thick * 0.7, h / 2 + ry - thick * 0.7], outline=255, width=max(2, int(thick * 0.28)))
    shade = ImageChops.multiply(shade, band).filter(ImageFilter.GaussianBlur(S))
    base.paste((110, 64, 12), (0, 0), shade.point(lambda v: int(v * 0.55)))
    # Specular highlight along the upper left of the band.
    hl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(hl).arc([w / 2 - rx + thick * 0.2, h / 2 - ry + thick * 0.2, w / 2 + rx - thick * 0.2, h / 2 + ry - thick * 0.2], 190, 262, fill=255, width=max(2, int(thick * 0.22)))
    hl = ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(S * 0.6)), band)
    base.paste((255, 250, 220), (0, 0), hl.point(lambda v: int(v * 0.9)))
    return base.rotate(tilt, resample=Image.BICUBIC, expand=False)


def main():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Glass bauble: warm amber rim fading to a dusky scene inside.
    sphere = grad((2 * R, 2 * R), [(0, (255, 214, 120)), (0.5, (196, 124, 36)), (1, (110, 62, 18))], 70)
    img.paste(sphere, (CX - R, CY - R), mask_circle(R, R, R, (2 * R, 2 * R)))
    r2 = int(R * 0.88)
    inside = Image.new("RGB", (2 * r2, 2 * r2))
    inside.paste(grad((2 * r2, 2 * r2), [(0, (58, 52, 92)), (0.55, (214, 150, 110)), (1, (240, 200, 140))], 90))
    d = ImageDraw.Draw(inside)
    # Distant mountain silhouettes.
    d.polygon([(0, r2 + 20), (r2 * 0.45, r2 * 0.55), (r2 * 0.7, r2 * 0.8), (r2 * 1.1, r2 * 0.45), (r2 * 1.6, r2 * 0.85), (2 * r2, r2 * 0.7), (2 * r2, 2 * r2), (0, 2 * r2)], fill=(92, 84, 112))
    d.polygon([(0, r2 * 1.3), (r2 * 0.6, r2 * 1.0), (r2 * 1.2, r2 * 1.25), (2 * r2, r2 * 1.05), (2 * r2, 2 * r2), (0, 2 * r2)], fill=(52, 70, 56))
    scene = inside.convert('RGBA'); scene.putalpha(mask_circle(r2, r2, r2, (2 * r2, 2 * r2)))
    img.alpha_composite(scene, (CX - r2, CY - r2))

    # Pine bough across the lower third, with needles.
    bough = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bough)
    by = lambda x: CY + 66 * S + 14 * S * math.sin((x - CX) / (46 * S))
    bd.line([(x, by(x)) for x in range(CX - r2, CX + r2, 4)], fill=(78, 48, 24, 255), width=7 * S)
    rnd = np.random.default_rng(5)
    for x in range(CX - r2, CX + r2, S):
        for side in (-1, 1):
            a = math.radians(rnd.uniform(15, 55)) * side
            ln = rnd.uniform(20, 34) * S
            y0 = by(x)
            col = (28 + int(rnd.uniform(0, 30)), 84 + int(rnd.uniform(0, 40)), 48, 255)
            bd.line([(x, y0), (x + ln * math.sin(a) * 0.5, y0 + ln * abs(math.cos(a)) * side * 0.9)], fill=col, width=int(1.6 * S))
    # Keep the bough inside the glass.
    inner_mask = mask_circle(CX, CY, r2, (W, H))
    img = Image.alpha_composite(img, Image.composite(bough, Image.new("RGBA", (W, H), (0, 0, 0, 0)), inner_mask))

    # Five separate bands in a loose arc, each a different size and tilt, none touching.
    specs = [(-94, 14, 38, -14), (-47, -4, 42, -6), (0, -14, 46, 0), (47, -4, 42, 6), (94, 14, 38, 14)]
    for dx, dy, dia, tilt in specs:
        t = ring(dia * S, tilt)
        x, y = CX + dx * S - t.width // 2, CY + dy * S - t.height // 2
        shadow = Image.new("RGBA", t.size, (0, 0, 0, 0))
        shadow.paste((30, 14, 4, 120), (0, 0), t.getchannel("A").filter(ImageFilter.GaussianBlur(3 * S)))
        img.alpha_composite(shadow, (x + 3 * S, y + 6 * S))
        img.alpha_composite(t, (x, y))

    # Glass sheen and rim.
    sheen = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sheen).ellipse([CX - R * 0.78, CY - R * 0.9, CX - R * 0.05, CY - R * 0.35], fill=120)
    sheen = sheen.filter(ImageFilter.GaussianBlur(10 * S))
    img.paste((255, 255, 255, 255), (0, 0), ImageChops.multiply(sheen, mask_circle(CX, CY, R, (W, H))))
    ImageDraw.Draw(img).ellipse([CX - R, CY - R, CX + R, CY + R], outline=(255, 226, 150, 255), width=3 * S)

    # Gold cap and hanging loop.
    cd = ImageDraw.Draw(img)
    cap_w, cap_h = 70 * S, 34 * S
    cap = grad((cap_w, cap_h), [(0, (255, 226, 140)), (0.5, (214, 150, 34)), (1, (128, 78, 16))], 0)
    img.paste(cap, (CX - cap_w // 2, CY - R - cap_h + 6 * S))
    for i in range(1, 6):
        x = CX - cap_w // 2 + i * cap_w // 6
        cd.line([(x, CY - R - cap_h + 10 * S), (x, CY - R + 2 * S)], fill=(120, 74, 14, 255), width=S)
    cd.ellipse([CX - 15 * S, CY - R - cap_h - 24 * S, CX + 15 * S, CY - R - cap_h + 12 * S], outline=(214, 150, 34, 255), width=4 * S)

    out = img.resize((W // S, H // S), Image.LANCZOS)
    path = HERE / "ornaments" / "day-05-drawn-draft.webp"
    out.save(path, "WEBP", quality=90)
    print(path.name, out.size)


if __name__ == "__main__":
    main()
