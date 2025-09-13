# core/art.py — zero-API, procedural pixel-art generator (v4)
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
    # keep contract: we embed title+text as 'prompt'
    return f"{scene_key} :: {scene_title} :: {scene_text}".strip()


def generate_pixel_art(prompt: str) -> bytes:
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

# NOTE: no 'jar' anywhere in keyword tags; only explicit overrides can add it.
KEYWORD_TAGS: Dict[str, Iterable[str]] = {
    # interiors
    "room": ["interior", "bed", "window", "lamp"],
    "home": ["interior", "bed", "window", "lamp"],
    "mirror": ["interior", "mirror", "desk"],
    "closet": ["interior", "hanger", "lamp"],
    "outfit": ["interior", "hanger", "lamp"],  # was 'mirror' → looks jar-ish; use hanger now
    "kitchen": ["interior", "counter", "kettle", "window"],
    "desk": ["interior", "desk", "lamp"],
    "cafe": ["interior", "counter", "mug", "window"],

    # exteriors
    "street": ["exterior", "buildings", "streetlamp", "sign"],
    "alley": ["exterior", "buildings", "sign"],
    "park": ["exterior", "trees", "bench"],
    "forest": ["exterior", "trees"],

    # vibes
    "night": ["stars"],
    "stars": ["stars"],
    "city": ["buildings"],

    # item-y vibes
    "pretty": ["interior", "desk", "lamp"],
    "accessor": ["interior", "desk", "lamp"],
}

# Strong defaults per known scene key (distinct looks)
SCENE_TAG_OVERRIDES: Dict[str, Iterable[str]] = {
    "intro": ["interior", "bed", "window", "lamp"],
    "home": ["interior", "bed", "window", "lamp"],
    "mirror": ["interior", "desk", "mirror", "lamp"],
    "kitchen": ["interior", "counter", "kettle", "window", "lamp"],
    "street": ["exterior", "buildings", "streetlamp", "sign"],
    "park": ["exterior", "trees", "bench"],
    "alley": ["exterior", "buildings", "sign"],
    "cafe": ["interior", "counter", "mug", "window", "lamp"],
    "boutique": ["exterior", "buildings", "sign"],
    "closet": ["interior", "hanger", "lamp"],

    # finale/save scenes — the ONLY places allowed to draw a jar
    "save": ["interior", "desk", "jar", "fireflies"],
    "rest": ["interior", "desk", "jar", "fireflies"],
    "home-rest": ["interior", "desk", "jar", "fireflies"],
}


def _hash_seed(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16) & 0xFFFFFFFF


class PixelComposer:
    """Builds a 512×512 pixel scene using simple shapes & a limited palette."""

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

        # bg gradient & shimmer
        self._bands(base, pal, rng)

        # foreground level — a tad higher to reduce empty headroom
        if "interior" in tags:
            self._draw_floor(draw, pal, h_frac=0.38)
        else:
            self._draw_ground(draw, pal, h_frac=0.32)

        # interior motifs
        if "interior" in tags:
            if "bed" in tags:      self._draw_bed(draw, pal, rng)
            if "window" in tags:   self._draw_window(draw, pal, rng)
            if "desk" in tags:     self._draw_desk(draw, pal, rng)
            if "mirror" in tags:   self._draw_wall_mirror(draw, pal, rng)
            if "counter" in tags:  self._draw_counter(draw, pal, rng)
            if "kettle" in tags:   self._draw_kettle(draw, pal, rng)
            if "lamp" in tags:     self._draw_lamp(draw, pal, rng)
            if "hanger" in tags:   self._draw_hanger_rack(draw, pal, rng)
            if "mug" in tags:      self._draw_mug(draw, pal, rng)
        # exterior motifs
        else:
            if "trees" in tags:        self._draw_trees(draw, pal, rng)
            if "bench" in tags:        self._draw_bench(draw, pal, rng)
            if "buildings" in tags:    self._draw_buildings(draw, pal, rng)
            if "streetlamp" in tags:   self._draw_streetlamp(draw, pal, rng)
            if "sign" in tags:         self._draw_sign(draw, pal, rng)

        # optional props
        if "jar" in tags:         self._draw_jar(draw, pal, rng)
        if "stars" in tags:       self._draw_starfield(draw, pal, rng)
        if "fireflies" in tags:   self._draw_fireflies(draw, pal, rng)

        # post — pixelize, scanlines, vignette
        base = self._pixelize(base, factor=5)
        base = self._scanlines(base, strength=22)
        base = self._vignette(base, amount=0.16)
        base = base.convert("P", palette=Image.ADAPTIVE, colors=24).convert("RGB")
        return base

    # ---------- parsing & palette ----------
    def _tags_from_prompt(self, prompt: str) -> List[str]:
        """
        Deterministic tag extraction:
        - start from overrides based on *scene key* (left of ::)
        - enrich with keywords from TITLE+TEXT only
        - 'jar' appears only if literal ' jar ' in title/text OR override asks for it
        - guarantee interior/exterior + at least one strong motif
        """
        p = prompt.lower()
        parts = [s.strip() for s in p.split("::", 2)]
        key, title, text = (parts + ["", "", ""])[:3]
        tags = set(SCENE_TAG_OVERRIDES.get(key, []))

        hay = f"{title} {text}"
        for kw, tg in KEYWORD_TAGS.items():
            if kw in hay:
                tags.update(tg)

        wants_jar = (" jar " in f" {hay} ") or ("fireflies" in hay) or ("jar" in tags)
        if not wants_jar:
            tags.discard("jar")
            # stars are fine at night outdoors; indoors keep it clean
            if "interior" in tags:
                tags.discard("fireflies")

        # ensure realm
        if not any(t in tags for t in ("interior", "exterior")):
            if any(t in tags for t in ("trees", "buildings", "sign", "bench", "streetlamp")):
                tags.add("exterior")
            else:
                tags.add("interior")

        # ensure at least one strong motif per realm
        if "interior" in tags and not any(
                t in tags for t in ("bed", "desk", "counter", "window", "mirror", "hanger", "lamp")):
            tags.update(["desk", "lamp"])
        if "exterior" in tags and not any(t in tags for t in ("trees", "buildings", "bench", "streetlamp", "sign")):
            tags.update(["buildings", "streetlamp"])

        return list(tags)

    def _pick_palette(self, tags: List[str], rng: random.Random) -> Palette:
        if "forest" in tags or "trees" in tags: return PALETTES[1]
        if "interior" in tags:                  return PALETTES[2]
        if "dawn" in tags or "stars" in tags:   return PALETTES[3]
        return rng.choice(PALETTES)

    # ---------- composition primitives ----------
    def _bands(self, img: Image.Image, pal: Palette, rng: random.Random):
        w, h = img.size;
        px = img.load()
        for y in range(h):
            t = y / h
            r = int(pal.bg[0] + (pal.accent2[0] - pal.bg[0]) * t * 0.28)
            g = int(pal.bg[1] + (pal.accent2[1] - pal.bg[1]) * t * 0.28)
            b = int(pal.bg[2] + (pal.accent2[2] - pal.bg[2]) * t * 0.28)
            for x in range(w):
                px[x, y] = (min(255, r + 10), min(255, g + 10), min(255, b + 10)) if ((x + y) % 47) == 0 else (r, g, b)

    def _draw_floor(self, d: ImageDraw.ImageDraw, pal: Palette, h_frac: float = 0.38):
        w, h = d.im.size;
        y = int(h * (1 - h_frac))
        d.rectangle([0, y, w, h], fill=(pal.bg[0] + 10, pal.bg[1] + 6, pal.bg[2] + 14), outline=pal.accent2)

    def _draw_ground(self, d: ImageDraw.ImageDraw, pal: Palette, h_frac: float = 0.32):
        w, h = d.im.size;
        y = int(h * (1 - h_frac))
        d.rectangle([0, y, w, h], fill=(pal.bg[0] + 14, pal.bg[1] + 22, pal.bg[2] + 14))
        d.line([0, y - 1, w, y - 1], fill=pal.accent2)

    # ------- interior props -------
    def _draw_bed(self, d, pal, rng):
        w, h = d.im.size;
        y = int(h * 0.70);
        bw = int(w * 0.62);
        bh = 44;
        x0 = (w - bw) // 2
        d.rectangle([x0, y - bh, x0 + bw, y], fill=(pal.accent[0] // 2, pal.accent[1] // 2, pal.accent[2] // 2),
                    outline=pal.accent)
        for lx in (x0 + 16, x0 + bw - 24):
            d.rectangle([lx, y, lx + 10, y + 26], fill=(pal.accent[0] // 3, pal.accent[1] // 3, pal.accent[2] // 3))

    def _draw_window(self, d, pal, rng):
        w, h = d.im.size;
        ww, wh = int(w * 0.38), int(h * 0.26);
        x0 = int(w * 0.58);
        y0 = int(h * 0.26)
        d.rectangle([x0, y0, x0 + ww, y0 + wh], outline=pal.accent2)
        for _ in range(16):
            x = rng.randint(x0 + 6, x0 + ww - 6);
            y = rng.randint(y0 + 6, y0 + wh - 6)
            d.point((x, y), fill=(255, 240, 210))

    def _draw_lamp(self, d, pal, rng):
        w, h = d.im.size;
        x = int(w * 0.22);
        y = int(h * 0.66)
        d.line([x, y - 32, x, y], fill=pal.fg, width=2)
        d.ellipse([x - 10, y - 48, x + 10, y - 32], outline=pal.fg)

    def _draw_wall_mirror(self, d, pal, rng):
        # Wall-mounted oval mirror with highlight — no jar lid silhouette
        w, h = d.im.size;
        cx = int(w * 0.36);
        cy = int(h * 0.45);
        rw, rh = 52, 74
        d.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], outline=pal.accent2, width=2)
        # highlight slash
        d.line([cx - rw + 12, cy - rh + 18, cx - 8, cy - 10], fill=pal.accent2, width=2)

    def _draw_counter(self, d, pal, rng):
        w, h = d.im.size;
        y = int(h * 0.72);
        x0 = int(w * 0.12);
        x1 = int(w * 0.88)
        d.rectangle([x0, y - 34, x1, y], fill=(pal.accent2[0] // 3, pal.accent2[1] // 3, pal.accent2[2] // 3),
                    outline=pal.accent2)

    def _draw_kettle(self, d, pal, rng):
        w, h = d.im.size;
        x = int(w * 0.64);
        y = int(h * 0.60)
        d.ellipse([x - 14, y - 12, x + 14, y + 10], outline=pal.fg);
        d.rectangle([x - 6, y - 20, x + 6, y - 12], fill=pal.fg)

    def _draw_desk(self, d, pal, rng):
        w, h = d.im.size;
        y = int(h * 0.72);
        x0 = int(w * 0.18);
        x1 = int(w * 0.82)
        d.rectangle([x0, y - 40, x1, y], fill=(pal.accent[0] // 2, pal.accent[1] // 2, pal.accent[2] // 2),
                    outline=pal.accent)
        for lx in (x0 + 20, x1 - 28):
            d.rectangle([lx, y, lx + 8, y + 24], fill=(pal.accent[0] // 3, pal.accent[1] // 3, pal.accent[2] // 3))

    def _draw_hanger_rack(self, d, pal, rng):
        w, h = d.im.size;
        y = int(h * 0.66);
        x0 = int(w * 0.30);
        x1 = int(w * 0.70)
        d.line([x0, y, x1, y], fill=pal.accent2, width=2)  # rail
        # simple dress
        cx = (x0 + x1) // 2;
        top = y + 2
        d.polygon([(cx, top), (cx - 18, top + 38), (cx + 18, top + 38)], outline=pal.fg)
        d.line([cx - 26, y, cx - 14, y + 16], fill=pal.accent2, width=2)  # hanger hook

    def _draw_mug(self, d, pal, rng):
        w, h = d.im.size;
        x = int(w * 0.62);
        y = int(h * 0.66)
        d.rectangle([x - 10, y - 14, x + 10, y], outline=pal.fg)
        d.arc([x + 10, y - 12, x + 22, y - 2], 270, 90, fill=pal.fg)

    # ------- exterior props -------
    def _draw_trees(self, d, pal, rng):
        w, h = d.im.size;
        base_y = int(h * 0.74)
        for i in range(6):
            x = int(w * (0.08 + i * 0.14 + rng.random() * 0.05));
            size = rng.randint(40, 90)
            self._pinetree(d, (x, base_y), size, pal)

    def _pinetree(self, d, base_xy, size, pal):
        x, y = base_xy
        d.rectangle([x - 3, y - size // 6, x + 3, y], fill=(60, 40, 50))
        for k in range(4):
            w = size - k * (size // 5);
            hh = size // 6
            d.polygon([(x - w // 2, y - k * hh - hh), (x, y - k * hh - size // 3), (x + w // 2, y - k * hh - hh)],
                      fill=(int(pal.accent2[0] * 0.6), int(pal.accent2[1] * 0.9), int(pal.accent2[2] * 0.7)))

    def _draw_bench(self, d, pal, rng):
        w, h = d.im.size;
        y = int(h * 0.72);
        x0 = int(w * 0.30);
        x1 = int(w * 0.70)
        d.rectangle([x0, y - 10, x1, y], outline=pal.accent2)
        d.rectangle([x0, y - 24, x1, y - 16], outline=pal.accent2)

    def _draw_buildings(self, d, pal, rng):
        w, h = d.im.size;
        base_y = int(h * 0.78);
        x = int(w * 0.06)
        while x < w * 0.94:
            bw = rng.randint(60, 110);
            bh = rng.randint(90, 160)
            d.rectangle([x, base_y - bh, x + bw, base_y],
                        fill=(pal.accent2[0] // 3, pal.accent2[1] // 3, pal.accent2[2] // 3), outline=pal.accent2)
            for r in range(2, bh // 24):
                for c in range(2, bw // 20):
                    wx = x + c * 18;
                    wy = base_y - bh + r * 20
                    if rng.random() < 0.6: d.rectangle([wx, wy, wx + 8, wy + 10], fill=pal.fg)
            x += bw + 14

    def _draw_streetlamp(self, d, pal, rng):
        w, h = d.im.size;
        x = int(w * 0.20);
        y = int(h * 0.58)
        d.line([x, y - 40, x, y + 16], fill=pal.accent2, width=2)
        d.ellipse([x - 8, y - 52, x + 8, y - 36], outline=pal.accent2)

    def _draw_sign(self, d, pal, rng):
        w, h = d.im.size;
        x = int(w * 0.65);
        y = int(h * 0.52)
        d.rectangle([x, y, x + 80, y + 24], outline=pal.fg);
        d.line([x + 6, y + 12, x + 74, y + 12], fill=pal.fg, width=2)

    # ------- optional props -------
    def _draw_jar(self, d, pal, rng):
        w, h = d.im.size;
        jar_w, jar_h = 70, 90;
        x0 = int(w * 0.25);
        y0 = int(h * 0.60)
        d.rounded_rectangle([x0, y0 - jar_h, x0 + jar_w, y0], radius=12, outline=pal.fg, width=2)
        d.rectangle([x0 + 10, y0 - jar_h - 10, x0 + jar_w - 10, y0 - jar_h + 2], fill=pal.fg)

    def _draw_starfield(self, d, pal, rng):
        w, h = d.im.size
        for _ in range(40):
            x = rng.randint(int(w * 0.1), int(w * 0.9));
            y = rng.randint(int(h * 0.2), int(h * 0.6))
            d.point((x, y), fill=(255, 240, 210))

    def _draw_fireflies(self, d, pal, rng):
        w, h = d.im.size
        for _ in range(36):
            x = rng.randint(int(w * 0.1), int(w * 0.9));
            y = rng.randint(int(h * 0.2), int(h * 0.8))
            d.point((x, y), fill=(255, 240, 140));
            d.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 240, 140))

    # ---------- post FX ----------
    def _pixelize(self, img: Image.Image, factor: int = 5) -> Image.Image:
        w, h = img.size;
        small = img.resize((max(1, w // factor), max(1, h // factor)), Image.BILINEAR)
        return small.resize((w, h), Image.NEAREST)

    def _scanlines(self, img: Image.Image, strength: int = 22) -> Image.Image:
        w, h = img.size;
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0));
        d = ImageDraw.Draw(overlay)
        for y in range(0, h, 2): d.line([0, y, w, y], fill=(0, 0, 0, strength))
        return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    def _vignette(self, img: Image.Image, amount: float = 0.16) -> Image.Image:
        w, h = img.size;
        rad = math.sqrt(w * w + h * h) / 2
        mask = Image.new("L", (w, h), 0);
        d = ImageDraw.Draw(mask)
        d.ellipse([int(-rad * 0.2), int(-rad * 0.2), int(w + rad * 0.2), int(h + rad * 0.2)], fill=int(255 * amount))
        blur = mask.filter(ImageFilter.GaussianBlur(radius=40))
        return Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), img, blur).convert("RGB")
