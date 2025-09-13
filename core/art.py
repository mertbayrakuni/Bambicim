# core/art.py — zero-API, procedural pixel-art generator
import hashlib
import io
import math
import random
import threading
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from PIL import Image, ImageDraw, ImageFilter  # Pillow only


# ---------------------------
# Public helpers (stable API)
# ---------------------------

def _prompt_for(scene_key: str, scene_title: str, scene_text: str) -> str:
    """Keep the same contract the views expect; we embed title+text as 'prompt'."""
    return f"{scene_key} :: {scene_title} :: {scene_text}".strip()


def generate_pixel_art(prompt: str) -> bytes:
    """Entry point used by views: returns WEBP bytes of a 512x512 pixel-style scene."""
    composer = PixelComposer(size=512)
    img = composer.render(prompt)
    with io.BytesIO() as buf:
        img.save(buf, format="WEBP", quality=92, method=6)
        return buf.getvalue()


def run_in_thread(fn, *args, **kwargs):
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t


# ---------------------------
# Core: procedural generator
# ---------------------------

@dataclass
class Palette:
    name: str
    bg: Tuple[int, int, int]
    fg: Tuple[int, int, int]
    accent: Tuple[int, int, int]
    accent2: Tuple[int, int, int]


PALETTES: List[Palette] = [
    Palette("twilight", (10, 2, 20), (248, 144, 230), (255, 182, 238), (155, 120, 255)),
    Palette("forest", (7, 12, 10), (180, 240, 180), (140, 208, 140), (80, 180, 140)),
    Palette("home", (18, 8, 18), (255, 200, 240), (255, 170, 210), (210, 150, 255)),
    Palette("dawn", (20, 6, 28), (255, 210, 150), (255, 160, 120), (255, 100, 180)),
]

# keyword → tag groups for quick “layout decisions”
KEYWORD_TAGS: Dict[str, Iterable[str]] = {
    "home": ["interior", "desk", "jar"],
    "save": ["interior", "desk", "jar"],
    "forest": ["exterior", "trees", "fireflies"],
    "shop": ["interior", "shelves"],
    "street": ["exterior", "buildings"],
    "night": ["fireflies"],
    "back": ["interior"],  # "Back home..."
    "desk": ["desk", "jar"],
    "jar": ["jar", "fireflies"],
    "tree": ["trees"],
    "fireflies": ["fireflies"],
}


def _hash_seed(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16) & 0xFFFFFFFF


class PixelComposer:
    """
    Builds a 512x512 'pixel' scene using simple shapes, dithering, and a limited palette.
    Deterministic: prompt -> seed -> same composition every time.
    """

    def __init__(self, size: int = 512):
        self.size = size

    # ---------- public ----------
    def render(self, prompt: str) -> Image.Image:
        seed = _hash_seed(prompt)
        rng = random.Random(seed)
        tags = self._tags_from_prompt(prompt)
        pal = self._pick_palette(tags, rng)

        base = Image.new("RGB", (self.size, self.size), pal.bg)
        draw = ImageDraw.Draw(base)

        # big background gradient bands for attitude
        self._bands(base, pal, rng)

        # layout: foreground/platform area
        if "interior" in tags:
            self._draw_floor(draw, pal, h_frac=0.3)
        else:
            self._draw_ground(draw, pal, h_frac=0.25)

        # motifs (pick based on tags)
        if "desk" in tags:
            self._draw_desk(draw, pal, rng)
        if "shelves" in tags:
            self._draw_shelves(draw, pal, rng)
        if "trees" in tags:
            self._draw_trees(draw, pal, rng)
        if "buildings" in tags:
            self._draw_buildings(draw, pal, rng)
        if "jar" in tags:
            self._draw_jar(draw, pal, rng)
        if "fireflies" in tags:
            self._draw_fireflies(draw, pal, rng)

        # pixel-ify: shrink & expand with NEAREST to lock in chunky pixels
        base = self._pixelize(base, factor=6)

        # subtle scanlines / vignette for retro feel
        base = self._scanlines(base, strength=28)
        base = self._vignette(base, amount=0.18)

        # final limited palette quantize (keeps filesize tiny)
        base = base.convert("P", palette=Image.ADAPTIVE, colors=24).convert("RGB")
        return base

    # ---------- parsing & palette ----------
    def _tags_from_prompt(self, prompt: str) -> List[str]:
        p = prompt.lower()
        tags = set()
        for k, tg in KEYWORD_TAGS.items():
            if k in p:
                for t in tg:
                    tags.add(t)
        # default fallback
        if not tags:
            tags.update(["interior", "desk", "jar"])
        return list(tags)

    def _pick_palette(self, tags: List[str], rng: random.Random) -> Palette:
        if "forest" in tags or "trees" in tags:
            return PALETTES[1]
        if "interior" in tags or "desk" in tags:
            return PALETTES[2]
        if "dawn" in tags:
            return PALETTES[3]
        return rng.choice(PALETTES)

    # ---------- composition primitives ----------
    def _bands(self, img: Image.Image, pal: Palette, rng: random.Random):
        w, h = img.size
        base = img.load()
        for y in range(h):
            # a simple vertical gradient into bg with slight noise
            t = y / h
            r = int(pal.bg[0] + (pal.accent2[0] - pal.bg[0]) * t * 0.25)
            g = int(pal.bg[1] + (pal.accent2[1] - pal.bg[1]) * t * 0.25)
            b = int(pal.bg[2] + (pal.accent2[2] - pal.bg[2]) * t * 0.25)
            for x in range(w):
                if ((x + y) % 47) == 0:
                    # faint diagonal shimmer
                    rr = min(255, r + 10)
                    gg = min(255, g + 10)
                    bb = min(255, b + 10)
                    base[x, y] = (rr, gg, bb)
                else:
                    base[x, y] = (r, g, b)

    def _draw_floor(self, draw: ImageDraw.ImageDraw, pal: Palette, h_frac: float = 0.3):
        w, h = draw.im.size
        y = int(h * (1 - h_frac))
        draw.rectangle([0, y, w, h], fill=(pal.bg[0] + 8, pal.bg[1] + 4, pal.bg[2] + 10), outline=pal.accent2)

    def _draw_ground(self, draw: ImageDraw.ImageDraw, pal: Palette, h_frac: float = 0.25):
        w, h = draw.im.size
        y = int(h * (1 - h_frac))
        draw.rectangle([0, y, w, h], fill=(pal.bg[0] + 12, pal.bg[1] + 20, pal.bg[2] + 12))
        # hint of horizon line
        draw.line([0, y - 1, w, y - 1], fill=pal.accent2)

    def _draw_desk(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        y = int(h * 0.72)
        x0 = int(w * 0.18)
        x1 = int(w * 0.82)
        draw.rectangle([x0, y - 40, x1, y], fill=(pal.accent[0] // 2, pal.accent[1] // 2, pal.accent[2] // 2),
                       outline=pal.accent)
        # legs
        leg = 8
        for lx in (x0 + 20, x1 - 20 - leg):
            draw.rectangle([lx, y, lx + leg, y + 26], fill=(pal.accent[0] // 3, pal.accent[1] // 3, pal.accent[2] // 3))

    def _draw_shelves(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        y = int(h * 0.38)
        for i in range(2):
            yy = y + i * 26
            draw.rectangle([int(w * 0.65), yy, int(w * 0.92), yy + 10], outline=pal.accent2)
            # little books/boxes
            for j in range(5):
                bx = int(w * 0.67) + j * 20
                by = yy - 12 + (j % 2) * 4
                draw.rectangle([bx, by, bx + 12, by + 12],
                               fill=(pal.fg[0] - j * 6, pal.fg[1] - j * 5, pal.fg[2] - j * 3))

    def _draw_trees(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        base_y = int(h * 0.72)
        for i in range(6):
            x = int(w * (0.08 + i * 0.14 + (rng.random() * 0.05)))
            size = rng.randint(40, 90)
            self._pinetree(draw, (x, base_y), size, pal)

    def _pinetree(self, draw, base_xy, size, pal):
        x, y = base_xy
        # trunk
        draw.rectangle([x - 3, y - size // 6, x + 3, y], fill=(60, 40, 50))
        # canopy
        for k in range(4):
            w = size - k * (size // 5)
            hh = size // 6
            draw.polygon([(x - w // 2, y - k * hh - hh),
                          (x, y - k * hh - size // 3),
                          (x + w // 2, y - k * hh - hh)],
                         fill=(int(pal.accent2[0] * 0.6), int(pal.accent2[1] * 0.9), int(pal.accent2[2] * 0.7)))

    def _draw_buildings(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        base_y = int(h * 0.75)
        for i in range(4):
            bw = rng.randint(60, 110)
            bh = rng.randint(90, 160)
            x0 = int(w * 0.05) + i * (bw + 20)
            y0 = base_y - bh
            draw.rectangle([x0, y0, x0 + bw, base_y],
                           fill=(pal.accent2[0] // 3, pal.accent2[1] // 3, pal.accent2[2] // 3),
                           outline=pal.accent2)
            # windows
            for r in range(2, bh // 24):
                for c in range(2, bw // 20):
                    wx = x0 + c * 18
                    wy = y0 + r * 20
                    if rng.random() < 0.6:
                        draw.rectangle([wx, wy, wx + 8, wy + 10], fill=pal.fg)

    def _draw_jar(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        jar_w, jar_h = 70, 90
        x0 = int(w * 0.25)
        y0 = int(h * 0.60)
        draw.rounded_rectangle([x0, y0 - jar_h, x0 + jar_w, y0], radius=12, outline=pal.fg, width=2)
        draw.rectangle([x0 + 10, y0 - jar_h - 10, x0 + jar_w - 10, y0 - jar_h + 2], fill=pal.fg)

    def _draw_fireflies(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        for _ in range(40):
            x = rng.randint(int(w * 0.1), int(w * 0.9))
            y = rng.randint(int(h * 0.2), int(h * 0.8))
            draw.point((x, y), fill=(255, 240, 140))
            # tiny glow
            draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 240, 140))

    # ---------- post effects ----------
    def _pixelize(self, img: Image.Image, factor: int = 6) -> Image.Image:
        w, h = img.size
        small = img.resize((max(1, w // factor), max(1, h // factor)), Image.BILINEAR)
        return small.resize((w, h), Image.NEAREST)

    def _scanlines(self, img: Image.Image, strength: int = 24) -> Image.Image:
        w, h = img.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        for y in range(0, h, 2):
            d.line([0, y, w, y], fill=(0, 0, 0, strength))
        return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    def _vignette(self, img: Image.Image, amount: float = 0.2) -> Image.Image:
        w, h = img.size
        rad = math.sqrt(w * w + h * h) / 2
        mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mask)
        d.ellipse([int(-rad * 0.2), int(-rad * 0.2), int(w + rad * 0.2), int(h + rad * 0.2)], fill=int(255 * amount))
        blur = mask.filter(ImageFilter.GaussianBlur(radius=40))
        return Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), img, blur).convert("RGB")
