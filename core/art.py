# core/art.py — zero-API, procedural pixel-art generator (v2)
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

# keyword → tag groups for layout/props
KEYWORD_TAGS: Dict[str, Iterable[str]] = {
    # interiors
    "room": ["interior", "bed", "window", "lamp"],
    "home": ["interior", "bed", "window"],  # no jar by default anymore
    "mirror": ["interior", "desk", "mirror"],
    "kitchen": ["interior", "counter", "kettle", "window"],
    "save": ["interior", "desk"],  # keep minimal
    # exteriors
    "street": ["exterior", "buildings", "sign"],
    "alley": ["exterior", "buildings"],
    "park": ["exterior", "trees"],
    "forest": ["exterior", "trees", "fireflies"],
    "cafe": ["exterior", "buildings", "sign"],
    "boutique": ["exterior", "buildings", "sign"],
    # singles
    "night": ["fireflies"],
    "desk": ["interior", "desk"],
    "jar": ["jar", "fireflies"],
    "tree": ["trees"],
    "fireflies": ["fireflies"],
}

# Only these scene KEYS may render a jar (and optionally fireflies)
ALLOWED_JAR_KEYS = {"home", "save", "rest", "home-rest"}


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

        # background gradient & shimmer
        self._bands(base, pal, rng)

        # layout: foreground/platform area (raise it a bit to reduce empty top)
        if "interior" in tags:
            self._draw_floor(draw, pal, h_frac=0.36)
        else:
            self._draw_ground(draw, pal, h_frac=0.30)

        # ---- motifs (interior/exterior) ----
        # interior sets: choose a couple based on tags
        if "interior" in tags:
            if "bed" in tags:      self._draw_bed(draw, pal, rng)
            if "window" in tags:   self._draw_window(draw, pal, rng)
            if "desk" in tags:     self._draw_desk(draw, pal, rng)
            if "mirror" in tags:   self._draw_mirror(draw, pal, rng)
            if "counter" in tags:  self._draw_counter(draw, pal, rng)
            if "kettle" in tags:   self._draw_kettle(draw, pal, rng)
            if "lamp" in tags:     self._draw_lamp(draw, pal, rng)
        else:
            if "trees" in tags:       self._draw_trees(draw, pal, rng)
            if "buildings" in tags:   self._draw_buildings(draw, pal, rng)
            if "sign" in tags:        self._draw_sign(draw, pal, rng)

        # optional props
        if "jar" in tags:          self._draw_jar(draw, pal, rng)
        if "fireflies" in tags:    self._draw_fireflies(draw, pal, rng)

        # pixel-ify: shrink & expand with NEAREST to lock in chunky pixels
        base = self._pixelize(base, factor=5)

        # subtle scanlines / vignette for retro feel
        base = self._scanlines(base, strength=22)
        base = self._vignette(base, amount=0.16)

        # final limited palette quantize (keeps filesize tiny)
        base = base.convert("P", palette=Image.ADAPTIVE, colors=24).convert("RGB")
        return base

    # ---------- parsing & palette ----------
    def _tags_from_prompt(self, prompt: str) -> List[str]:
        """
        Extract tags from the combined "key :: title :: text" prompt.
        - Uses KEYWORD_TAGS matches across key/title/text.
        - Enforces 'jar' (and usually 'fireflies') only on whitelisted keys.
        - Falls back to a tame interior scene if nothing matched.
        """
        p = prompt.lower()
        # try to grab the scene key from 'key :: title :: text'
        key_part = p.split("::", 1)[0].strip() if "::" in p else p.strip()

        tags = set()
        for kw, tg in KEYWORD_TAGS.items():
            if kw in p:
                for t in tg:
                    tags.add(t)

        # If nothing matched at all, try a gentle default (no jar)
        if not tags:
            # If the key itself looks like one of our known keywords, seed from it
            if key_part in KEYWORD_TAGS:
                tags.update(KEYWORD_TAGS[key_part])
            else:
                tags.update(["interior", "bed", "window"])  # safe default

        # Hard rules:
        # 1) JAR only on allowed keys
        if "jar" in tags and key_part not in ALLOWED_JAR_KEYS:
            tags.discard("jar")

        # 2) FIRELIES are allowed outdoors or jar-scenes; otherwise drop
        if "fireflies" in tags:
            is_outdoor = any(t in tags for t in ("trees", "buildings", "exterior"))
            if (key_part not in ALLOWED_JAR_KEYS) and not is_outdoor:
                tags.discard("fireflies")

        # 3) Ensure we always have an interior/exterior base tag
        if not any(t in tags for t in ("interior", "exterior")):
            # guess from context; default to interior
            if any(t in tags for t in ("trees", "buildings", "sign")):
                tags.add("exterior")
            else:
                tags.add("interior")

        return list(tags)

    def _pick_palette(self, tags: List[str], rng: random.Random) -> Palette:
        if "forest" in tags or "trees" in tags:
            return PALETTES[1]
        if "interior" in tags:
            return PALETTES[2]
        if "dawn" in tags:
            return PALETTES[3]
        return rng.choice(PALETTES)

    # ---------- composition primitives ----------
    def _bands(self, img: Image.Image, pal: Palette, rng: random.Random):
        w, h = img.size
        base = img.load()
        for y in range(h):
            t = y / h
            r = int(pal.bg[0] + (pal.accent2[0] - pal.bg[0]) * t * 0.28)
            g = int(pal.bg[1] + (pal.accent2[1] - pal.bg[1]) * t * 0.28)
            b = int(pal.bg[2] + (pal.accent2[2] - pal.bg[2]) * t * 0.28)
            for x in range(w):
                if ((x + y) % 47) == 0:
                    base[x, y] = (min(255, r + 10), min(255, g + 10), min(255, b + 10))
                else:
                    base[x, y] = (r, g, b)

    def _draw_floor(self, draw: ImageDraw.ImageDraw, pal: Palette, h_frac: float = 0.36):
        w, h = draw.im.size
        y = int(h * (1 - h_frac))
        draw.rectangle([0, y, w, h], fill=(pal.bg[0] + 10, pal.bg[1] + 6, pal.bg[2] + 14), outline=pal.accent2)

    def _draw_ground(self, draw: ImageDraw.ImageDraw, pal: Palette, h_frac: float = 0.30):
        w, h = draw.im.size
        y = int(h * (1 - h_frac))
        draw.rectangle([0, y, w, h], fill=(pal.bg[0] + 14, pal.bg[1] + 22, pal.bg[2] + 14))
        draw.line([0, y - 1, w, y - 1], fill=pal.accent2)

    # ------- interior props -------
    def _draw_bed(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        y = int(h * 0.70)
        bed_w = int(w * 0.62)
        bed_h = 44
        x0 = int((w - bed_w) / 2)
        draw.rectangle([x0, y - bed_h, x0 + bed_w, y],
                       fill=(pal.accent[0] // 2, pal.accent[1] // 2, pal.accent[2] // 2),
                       outline=pal.accent)
        # legs
        for lx in (x0 + 16, x0 + bed_w - 24):
            draw.rectangle([lx, y, lx + 10, y + 26], fill=(pal.accent[0] // 3, pal.accent[1] // 3, pal.accent[2] // 3))

    def _draw_window(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        ww, wh = int(w * 0.38), int(h * 0.26)
        x0 = int(w * 0.58)
        y0 = int(h * 0.26)
        draw.rectangle([x0, y0, x0 + ww, y0 + wh], outline=pal.accent2)
        # simple “stars”
        for _ in range(16):
            x = rng.randint(x0 + 6, x0 + ww - 6)
            y = rng.randint(y0 + 6, y0 + wh - 6)
            draw.point((x, y), fill=(255, 240, 210))

    def _draw_lamp(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        x = int(w * 0.25)
        y = int(h * 0.66)
        draw.line([x, y - 30, x, y], fill=pal.fg, width=2)
        draw.ellipse([x - 10, y - 46, x + 10, y - 30], outline=pal.fg)

    def _draw_mirror(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        x = int(w * 0.33)
        y = int(h * 0.62)
        draw.rounded_rectangle([x - 28, y - 60, x + 28, y], radius=10, outline=pal.accent2, width=2)

    def _draw_counter(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        y = int(h * 0.72)
        x0 = int(w * 0.12)
        x1 = int(w * 0.88)
        draw.rectangle([x0, y - 34, x1, y], fill=(pal.accent2[0] // 3, pal.accent2[1] // 3, pal.accent2[2] // 3),
                       outline=pal.accent2)

    def _draw_kettle(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        x = int(w * 0.64)
        y = int(h * 0.62)
        draw.ellipse([x - 14, y - 12, x + 14, y + 10], outline=pal.fg)
        draw.rectangle([x - 6, y - 20, x + 6, y - 12], fill=pal.fg)

    def _draw_desk(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        y = int(h * 0.72)
        x0 = int(w * 0.18)
        x1 = int(w * 0.82)
        draw.rectangle([x0, y - 40, x1, y],
                       fill=(pal.accent[0] // 2, pal.accent[1] // 2, pal.accent[2] // 2),
                       outline=pal.accent)
        for lx in (x0 + 20, x1 - 28):
            draw.rectangle([lx, y, lx + 8, y + 24], fill=(pal.accent[0] // 3, pal.accent[1] // 3, pal.accent[2] // 3))

    # ------- exterior props -------
    def _draw_trees(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        base_y = int(h * 0.74)
        for i in range(6):
            x = int(w * (0.08 + i * 0.14 + (rng.random() * 0.05)))
            size = rng.randint(40, 90)
            self._pinetree(draw, (x, base_y), size, pal)

    def _pinetree(self, draw, base_xy, size, pal):
        x, y = base_xy
        draw.rectangle([x - 3, y - size // 6, x + 3, y], fill=(60, 40, 50))
        for k in range(4):
            w = size - k * (size // 5)
            hh = size // 6
            draw.polygon([(x - w // 2, y - k * hh - hh),
                          (x, y - k * hh - size // 3),
                          (x + w // 2, y - k * hh - hh)],
                         fill=(int(pal.accent2[0] * 0.6), int(pal.accent2[1] * 0.9), int(pal.accent2[2] * 0.7)))

    def _draw_buildings(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        base_y = int(h * 0.78)
        start = int(w * 0.06)
        x = start
        while x < w * 0.94:
            bw = rng.randint(60, 110)
            bh = rng.randint(90, 160)
            draw.rectangle([x, base_y - bh, x + bw, base_y],
                           fill=(pal.accent2[0] // 3, pal.accent2[1] // 3, pal.accent2[2] // 3),
                           outline=pal.accent2)
            # windows
            for r in range(2, bh // 24):
                for c in range(2, bw // 20):
                    wx = x + c * 18
                    wy = base_y - bh + r * 20
                    if rng.random() < 0.6:
                        draw.rectangle([wx, wy, wx + 8, wy + 10], fill=pal.fg)
            x += bw + 14

    def _draw_sign(self, draw: ImageDraw.ImageDraw, pal: Palette, rng: random.Random):
        w, h = draw.im.size
        x = int(w * 0.65)
        y = int(h * 0.52)
        draw.rectangle([x, y, x + 80, y + 24], outline=pal.fg)
        draw.line([x + 6, y + 12, x + 74, y + 12], fill=pal.fg, width=2)

    # ------- optional props -------
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
            draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 240, 140))

    # ---------- post effects ----------
    def _pixelize(self, img: Image.Image, factor: int = 5) -> Image.Image:
        w, h = img.size
        small = img.resize((max(1, w // factor), max(1, h // factor)), Image.BILINEAR)
        return small.resize((w, h), Image.NEAREST)

    def _scanlines(self, img: Image.Image, strength: int = 22) -> Image.Image:
        w, h = img.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        for y in range(0, h, 2):
            d.line([0, y, w, y], fill=(0, 0, 0, strength))
        return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    def _vignette(self, img: Image.Image, amount: float = 0.16) -> Image.Image:
        w, h = img.size
        rad = math.sqrt(w * w + h * h) / 2
        mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mask)
        d.ellipse([int(-rad * 0.2), int(-rad * 0.2), int(w + rad * 0.2), int(h + rad * 0.2)], fill=int(255 * amount))
        blur = mask.filter(ImageFilter.GaussianBlur(radius=40))
        return Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), img, blur).convert("RGB")
