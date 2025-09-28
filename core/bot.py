# core/bot.py — Bambi persona · Markdown native · files/inventory aware
from __future__ import annotations

import datetime as dt
import random
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import unicodedata

# --------------------------------------------------------------------------------------
# Site links
# --------------------------------------------------------------------------------------

BASE = "https://bambicim.com"
LINKS = {
    "home": f"{BASE}/",
    "work": f"{BASE}/#work",
    "game": f"{BASE}/#game",
    "contact": f"{BASE}/#contact",
    "login": f"{BASE}/accounts/login/",
    "signup": f"{BASE}/accounts/signup/",
    "profile": f"{BASE}/profile/",
    "privacy": f"{BASE}/privacy/",
    "terms": f"{BASE}/terms/",
}


# --------------------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------------------

def _now() -> dt.datetime:
    return dt.datetime.now()


def _today_str() -> str:
    return _now().strftime("%Y-%m-%d")


def _choose(xs: Sequence[str]) -> str:
    return random.choice(list(xs))


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _fmt_bytes(n: int) -> str:
    if n is None:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units) - 1:
        f /= 1024.0
        i += 1
    v = f"{f:.1f}".rstrip("0").rstrip(".")
    return f"{v} {units[i]}"


def _is_truthy(x: Any) -> bool:
    return str(x).lower() in {"1", "true", "yes", "y", "on"}


# --------------------------------------------------------------------------------------
# Language detection (TR/EN) + normalization
# --------------------------------------------------------------------------------------

_TR_CHARS = "ıİşŞğĞçÇöÖüÜ"
_TR_HINTS = {"merhaba", "selam", "giriş", "kayıt", "oyun", "tema", "envanter", "profil", "iletisim", "iletişim", "hata"}
_EN_HINTS = {"hi", "hello", "login", "signup", "game", "theme", "inventory", "profile", "contact", "work", "error"}

# translate() requires 1-char keys → use ord()
_TRANSLATE_TABLE = {
    # smart quotes / dashes / spaces
    ord("’"): "'",
    ord("‘"): "'",
    ord("“"): '"',
    ord("”"): '"',
    ord("–"): "-",
    ord("—"): "-",
    ord("…"): "...",
    ord("\u00A0"): " ",  # NBSP
    ord("\u200B"): "",  # ZWSP

    # Turkish letters → ASCII-ish for intent matching
    ord("İ"): "i",
    ord("I"): "i",  # only for matching; we don't display this back
    ord("ı"): "i",
    ord("Ş"): "s",
    ord("ş"): "s",
    ord("Ğ"): "g",
    ord("ğ"): "g",
    ord("Ç"): "c",
    ord("ç"): "c",
    ord("Ö"): "o",
    ord("ö"): "o",
    ord("Ü"): "u",
    ord("ü"): "u",
}


def _normalize(s: str) -> str:
    """Robust normalizer used only for intent matching (keeps emojis intact)."""
    if not s:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_TRANSLATE_TABLE)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip().lower()


def _detect_lang(q: str) -> str:
    if any(c in (q or "") for c in _TR_CHARS):
        return "tr"
    qn = _normalize(q)
    if any(w in qn.split() for w in _TR_HINTS):
        return "tr"
    if any(w in qn.split() for w in _EN_HINTS):
        return "en"
    return "tr"


# --------------------------------------------------------------------------------------
# i18n snippets
# --------------------------------------------------------------------------------------

I18N = {
    "hello": {"tr": "Selam tatlım! 💖", "en": "Hi sweetie! 💖"},
    "ask_help": {"tr": "Bugün sana nasıl yardımcı olabilirim?", "en": "How can I help you today?"},
    "iam": {
        "tr": "Ben **Bambi** — pembe takıntılı mini yardımcı. Siteyi avucumun içi gibi biliyorum 💅",
        "en": "I’m **Bambi** — your pink-obsessed mini helper. I know this site by heart 💅",
    },
    "site_intro_tr": (
        "Burası **Bambicim** — notlar, deneyler ve *Bambi Game*. ✨\n"
        f"- Çalışmalar: {LINKS['work']}\n"
        f"- Bambi Game: {LINKS['game']} *(kayıt olursan envanterin oluşur! 🎒)*\n"
        f"- Let’s talk: {LINKS['contact']}\n"
        "Üst sağdaki renk noktalarıyla temayı değiştirebilirsin 🎀"
    ),
    "site_intro_en": (
        "This is **Bambicim** — notes, experiments and *Bambi Game*. ✨\n"
        f"- Selected Work: {LINKS['work']}\n"
        f"- Bambi Game: {LINKS['game']} *(sign up to unlock inventory! 🎒)*\n"
        f"- Let’s talk: {LINKS['contact']}\n"
        "Use the color dots at top-right to switch theme 🎀"
    ),
    "inv_none": {
        "tr": "Envanter boş görünüyor. Biraz oyun? {game} 🎮",
        "en": "Your inventory looks empty. Try the game? {game} 🎮",
    },
    "inv_some": {
        "tr": "Envanterinde **{n}** çeşit var: {list}. {tip}",
        "en": "You have **{n}** item types: {list}. {tip}",
    },
    "ach_none": {
        "tr": "Henüz rozet yok. İlkini kapmak için oyunda birkaç seçim dene ✨",
        "en": "No badges yet — try a few choices in the game ✨",
    },
    "ach_some": {"tr": "Aferin! **{n}** rozetin var: {list}", "en": "Yay! You’ve got **{n}** badges: {list}"},
    "recommend": {"tr": "Önerim: {one} • {two}", "en": "My pick: {one} • {two}"},
    "debug_hint": {
        "tr": "Hata mı var? **F9** ile debug panelini aç; HTTP durumunu görürsün. 403 görürsen `/api/chat` için CSRF muafiyeti gerekli.",
        "en": "Seeing an error? Press **F9** to open the debug panel; you’ll see the HTTP status. If it’s 403, make `/api/chat` CSRF-exempt.",
    },
}


def _hello(lang: str) -> str:
    return I18N["hello"]["en" if lang == "en" else "tr"]


def _ask(lang: str) -> str:
    return I18N["ask_help"]["en" if lang == "en" else "tr"]


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------

def words_rx(ws: Iterable[str]) -> re.Pattern:
    return re.compile(r"\b(?:%s)\b" % "|".join(re.escape(w) for w in ws), re.I)


def _md_link(text: str, url: str) -> str:
    return f"[{text}]({url})"


def _md_code(s: str) -> str:
    return f"`{s}`"


def _md_blockquote(s: str) -> str:
    return "\n".join(["> " + line for line in s.splitlines()])


def _wrap_steps(*paras: str) -> str:
    """Return paragraphs separated by a blank line -> nice typewriter chunks."""
    return "\n\n".join(p.strip() for p in paras if p and str(p).strip())


# --------------------------------------------------------------------------------------
# Inventory / Achievements formatting
# --------------------------------------------------------------------------------------

def _fmt_items(items: Sequence[Union[dict, tuple]], lang: str) -> str:
    # items: list of dicts/tuples -> render “emoji name × qty”
    out: List[str] = []
    for r in list(items or [])[:6]:
        if isinstance(r, dict):
            slug = r.get("slug", "")
            name = r.get("name") or slug
            emoji = r.get("emoji", "")
            qty = r.get("qty", 1) or 1
        else:
            slug = r[0] if (isinstance(r, (list, tuple)) and len(r) > 0) else ""
            name = slug
            emoji = ""
            qty = (r[1] if (isinstance(r, (list, tuple)) and len(r) > 1) else 1) or 1
        label = f"{emoji} {name} × {qty}".strip()
        out.append(label)
    return ", ".join(out) if out else ""


def _inv_tip(lang: str, items: Sequence[Union[dict, tuple]]) -> str:
    text = "Tema **pink** ile daha tatlı görünür 💗" if lang != "en" else "Looks even cuter in the **pink** theme 💗"
    s = " ".join(((r.get("slug") if isinstance(r, dict) else (r[0] if r else "")) or "") for r in items if r)
    if re.search(r"crown|ta[cç]|krali|queen", s, re.I):
        text = "Taç sende — kraliçe modu **ON** 👑"
    elif re.search(r"heart|kalp", s, re.I):
        text = "Kalp toplamaya devam, aşk dolu ilerleme! 💖"
    elif re.search(r"star|yıldız", s, re.I):
        text = "Yıldızlar yol gösteriyor ⭐"
    return text


def _fmt_achievements(ach: Sequence[Union[dict, str]], lang: str) -> str:
    if not ach:
        return I18N["ach_none"]["en" if lang == "en" else "tr"]
    names = ", ".join(
        (f"{a.get('emoji', '')} {a.get('name', '')}".strip() if isinstance(a, dict) else str(a)) for a in ach[:8]
    )
    return I18N["ach_some"]["en" if lang == "en" else "tr"].format(n=len(ach), list=names)


# --------------------------------------------------------------------------------------
# File understanding (lightweight, backend passes `context["files_in"]`)
# Each file dict can include:
#   name, size, content_type, text (optional extracted), url (optional), is_image (bool)
# The view that handles uploads can fill these. We only analyze/summarize.
# --------------------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.I)
_TODO_RE = re.compile(r"(?im)^(?:\s*[-*]\s*)?(TODO|FIXME|NOTE)[:\-\s]+(.+)$")


def _peek_text(blob: str, limit: int = 1200) -> str:
    blob = (blob or "").strip()
    if len(blob) > limit:
        blob = blob[:limit].rsplit(" ", 1)[0] + " …"
    return blob


def _simple_stats(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    sentences = re.split(r"[.!?]+(?:\s|$)", text)
    wl = [len(w) for w in words] or [0]
    return {
        "chars": len(text),
        "words": len(words),
        "sentences": len([s for s in sentences if s.strip()]),
        "avg_wlen": round(sum(wl) / len(wl), 2) if wl else 0.0,
    }


def _list_head(xs: Sequence[str], n: int = 6) -> str:
    return ", ".join(x for x in xs[:n])


def _parse_csv_head(text: str) -> Tuple[List[str], int]:
    lines = [l for l in (text or "").splitlines() if l.strip()]
    if not lines:
        return ([], 0)
    header = re.split(r",|\t|\s*;\s*", lines[0].strip())
    rows = max(0, len(lines) - 1)
    return ([h.strip() for h in header if h.strip()], rows)


def _summarize_text_block(text: str, lang: str) -> str:
    st = _simple_stats(text)
    emails = list(dict.fromkeys(_EMAIL_RE.findall(text)))
    links = list(dict.fromkeys(_URL_RE.findall(text)))
    todos = [m.group(2).strip() for m in _TODO_RE.finditer(text)]

    if lang == "en":
        head = f"**Summary**\n- Words: **{st['words']}** · Sentences: **{st['sentences']}** · Avg word: **{st['avg_wlen']}**\n"
        if emails: head += f"- Emails: {_list_head(emails)}\n"
        if links: head += f"- Links: {_list_head(links)}\n"
        if todos: head += f"- TODOs: {_list_head(todos)}\n"
        return head.strip()
    else:
        head = f"**Özet**\n- Kelime: **{st['words']}** · Cümle: **{st['sentences']}** · Ortalama kelime: **{st['avg_wlen']}**\n"
        if emails: head += f"- E-postalar: {_list_head(emails)}\n"
        if links: head += f"- Linkler: {_list_head(links)}\n"
        if todos: head += f"- TODO: {_list_head(todos)}\n"
        return head.strip()


def _summarize_files(files: Sequence[Dict[str, Any]], lang: str) -> str:
    """
    Produce a markdown summary of files user attached.
    Expect each dict to have: name, size, content_type, text?, url?, is_image?
    """
    if not files:
        return ""

    lines: List[str] = []
    if lang == "en":
        lines.append("**Files received**:")
    else:
        lines.append("**Dosyalar alındı**:")

    def short_meta(f: Dict[str, Any]) -> str:
        ct = (f.get("content_type") or "").split(";")[0]
        sz = _fmt_bytes(int(f.get("size") or 0))
        nm = f.get("name") or "file"
        return f"- {nm} · {ct or 'unknown'} · {sz}"

    for f in files:
        lines.append(short_meta(f))

    # If we have any text-bearing doc, give a compact summary
    text_blobs: List[Tuple[str, str]] = []  # (name, text)
    for f in files:
        t = (f.get("text") or "").strip()
        if t:
            text_blobs.append((f.get("name") or "file", t))

    if text_blobs:
        if lang == "en":
            lines.append("\n**Quick peeks**:")
        else:
            lines.append("\n**Hızlı bakış**:")

        for nm, txt in text_blobs[:3]:
            preview = _peek_text(txt, 600)
            if lang == "en":
                lines.append(f"- **{nm}**\n\n{_md_blockquote(preview)}")
            else:
                lines.append(f"- **{nm}**\n\n{_md_blockquote(preview)}")

        # global summary
        joined = "\n\n".join(t for _, t in text_blobs)[:8000]
        lines.append("")
        lines.append(_summarize_text_block(joined, lang))

    # CSV hint
    for f in files:
        if (f.get("content_type") or "").lower() in {"text/csv", "application/vnd.ms-excel"} or re.search(
                r"\.(csv|tsv)$", f.get("name") or "", re.I
        ):
            cols, rows = _parse_csv_head(f.get("text") or "")
            if cols:
                if lang == "en":
                    lines.append(f"\n**CSV**: columns → {', '.join(cols)} · rows ≈ **{rows}**")
                else:
                    lines.append(f"\n**CSV**: sütunlar → {', '.join(cols)} · satır ≈ **{rows}**")

    # Image hint
    img_count = sum(
        1 for f in files if _is_truthy(f.get("is_image")) or str(f.get("content_type", "")).startswith("image/"))
    if img_count:
        if lang == "en":
            lines.append(f"\n_I added a gallery with {img_count} {_plural(img_count, 'image', 'images')}_ above._")
        else:
            lines.append(f"\n_Yukarıya {img_count} {_plural(img_count, 'görsel', 'görsel')} galerisi ekledim._")

    return "\n".join(lines).strip()


def _extract_from_files(files: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    emails: List[str] = []
    links: List[str] = []
    todos: List[str] = []
    for f in files or []:
        blob = f.get("text") or ""
        emails.extend(_EMAIL_RE.findall(blob))
        links.extend(_URL_RE.findall(blob))
        todos.extend([m.group(2).strip() for m in _TODO_RE.finditer(blob)])

    # dedupe preserving order
    def uniq(xs: Iterable[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for x in xs:
            if x not in seen:
                out.append(x)
                seen.add(x)
        return out

    return {"emails": uniq(emails), "links": uniq(links), "todos": uniq(todos)}


# --------------------------------------------------------------------------------------
# Persona / FAQ / Commands
# --------------------------------------------------------------------------------------

FAQ_EN = [
    (re.compile(r"\b(pricing|price|cost)\b"),
     "We don’t list pricing — each project is scoped uniquely. Best path is the " + _md_link("Let’s talk form", LINKS[
         "contact"]) + " or an email."),
    (re.compile(r"\b(contact|email)\b"),
     "You can reach us via the " + _md_link("contact form", LINKS["contact"]) + " or email."),
    (re.compile(r"\b(what is bambicim|about (the )?site)\b"), I18N["site_intro_en"]),
]

FAQ_TR = [
    (re.compile(r"\b(ucret|fiyat|pricing|maliyet)\b"),
     "Fiyatlar sabit değil — proje kapsamına göre belirlenir. En iyi yol " + _md_link("Let’s talk", LINKS[
         "contact"]) + " formu veya e-posta."),
    (re.compile(r"\b(iletisim|iletişim|e.?posta|mail)\b"),
     "Bize " + _md_link("iletişim formundan", LINKS["contact"]) + " ya da e-posta ile ulaşabilirsin."),
    (re.compile(r"\b(bambicim nedir|site hakkında)\b"), I18N["site_intro_tr"]),
]


def _faq_answer(q: str, lang: str) -> Optional[str]:
    bank = FAQ_EN if lang == "en" else FAQ_TR
    qn = _normalize(q)
    for rx, ans in bank:
        if rx.search(qn):
            return ans
    return None


HELP_EN = _wrap_steps(
    "**Bambi commands**",
    "- `/help` — this help\n"
    "- `/links` — key site links\n"
    "- `/about` — who I am & what this site is\n"
    "- `/inventory` · `/badges` — show your items / achievements (from *Bambi Game*)\n"
    "- `/reco` — where to go next\n"
    "- `/profile` · `/login` · `/signup` — quick auth links\n"
    "- `/theme pink|hot|white` — how to switch theme\n"
    "- `/time` · `/date` — quick clock\n"
    "- `/md` — markdown demo\n"
    "- `/summarize` — summarize attached files (TXT/MD/CSV/PDF*)\n"
    "- `/extract` — pull **emails** and **links** from attached files\n"
    "- `/todo` — list TODO/FIXME/NOTE lines from files\n"
    "- `/stats` — word/char stats for your message or file text\n\n"
    "_*PDF/DOCX extraction depends on backend text pass-through; I’ll use whatever text your server gives me._",
)

HELP_TR = _wrap_steps(
    "**Bambi komutları**",
    "- `/help` — bu yardım\n"
    "- `/links` — önemli linkler\n"
    "- `/about` — ben kimim, bu site ne\n"
    "- `/inventory` · `/badges` — envanter / rozetlerin (*Bambi Game*)\n"
    "- `/reco` — sırada ne var\n"
    "- `/profile` · `/login` · `/signup` — hızlı giriş kaydol\n"
    "- `/theme pink|hot|white` — tema nasıl değiştirilir\n"
    "- `/time` · `/date` — saat ve tarih\n"
    "- `/md` — markdown örneği\n"
    "- `/summarize` — ekli dosyaları özetle (TXT/MD/CSV/PDF*)\n"
    "- `/extract` — dosyalardan **e-posta** ve **linkleri** çıkar\n"
    "- `/todo` — dosyalardaki TODO/FIXME/NOTE satırları\n"
    "- `/stats` — mesajın veya dosya metninin istatistikleri\n\n"
    "_*PDF/DOCX özeti, sunucunun bana ilettiği metne bağlıdır._",
)


def _help(lang: str) -> str:
    return HELP_EN if lang == "en" else HELP_TR


def _links(lang: str) -> str:
    items = [
        ("Home", LINKS["home"]),
        ("Work", LINKS["work"]),
        ("Bambi Game", LINKS["game"]),
        ("Let’s talk", LINKS["contact"]),
        ("Profile", LINKS["profile"]),
        ("Login", LINKS["login"]),
        ("Sign up", LINKS["signup"]),
        ("Privacy", LINKS["privacy"]),
        ("Terms", LINKS["terms"]),
    ]
    if lang == "en":
        head = "**Key links**"
    else:
        head = "**Önemli linkler**"
    rows = [f"- {_md_link(t, u)}" for t, u in items]
    return _wrap_steps(head, "\n".join(rows))


def _about(lang: str) -> str:
    intro = I18N["site_intro_en" if lang == "en" else "site_intro_tr"]
    return _wrap_steps(I18N["iam"]["en" if lang == "en" else "tr"], intro)


def _theme_hint(lang: str, which: Optional[str] = None) -> str:
    which = (which or "").strip().lower()
    if lang == "en":
        base = "Use the little color **dots** at top-right."
        if which in {"pink", "hot", "white"}:
            return f"{base} Tap **{which}** for instant switch. ✨"
        return base + " Themes: *pink*, *hot*, *white*."
    else:
        base = "Üst sağdaki renk **noktalarını** kullan."
        if which in {"pink", "hot", "white"}:
            return f"{base} **{which}** temasına anında geçebilirsin. ✨"
        return base + " Temalar: *pink*, *hot*, *white*."


def _md_demo(lang: str) -> str:
    if lang == "en":
        return _wrap_steps(
            "**Markdown demo**",
            "- **Bold**, *italic*, `code`, ~~strike~~\n"
            "- Lists, links " + _md_link("bambicim.com", LINKS["home"]) + "\n"
                                                                          "```python\nprint('hi from Bambi')\n```"
        )
    else:
        return _wrap_steps(
            "**Markdown örneği**",
            "- **Kalın**, *italik*, `kod`, ~~üstü çizili~~\n"
            "- Listeler, linkler " + _md_link("bambicim.com", LINKS["home"]) + "\n"
                                                                               "```python\nprint('Bambi’den selam')\n```"
        )


# --------------------------------------------------------------------------------------
# Intent Handlers
# --------------------------------------------------------------------------------------

def H_greet(q, lang, ctx, user):
    sugg = _choose([
        f"**Bambi Game** → {LINKS['game']} 🎮",
        f"**Work** → {LINKS['work']} ✨",
        f"**Let’s talk** → {LINKS['contact']} 💌",
    ])
    return _wrap_steps(f"{_hello(lang)} {_ask(lang)}", I18N["iam"]["en" if lang == "en" else "tr"], sugg)


def H_whoami(q, lang, ctx, user):
    return _about(lang)


def H_site(q, lang, ctx, user):
    return I18N["site_intro_en" if lang == "en" else "site_intro_tr"]


def H_inv(q, lang, ctx, user):
    items = list(ctx.get("inv") or [])
    if not items:
        return I18N["inv_none"]["en" if lang == "en" else "tr"].format(game=LINKS["game"])
    return I18N["inv_some"]["en" if lang == "en" else "tr"].format(
        n=len(items), list=_fmt_items(items, lang), tip=_inv_tip(lang, items)
    )


def H_ach(q, lang, ctx, user):
    ach = list(ctx.get("ach") or [])
    return _fmt_achievements(ach, lang)


def H_reco(q, lang, ctx, user):
    a = f"Game → {LINKS['game']}"
    b = f"Work → {LINKS['work']}"
    if ctx.get("inv"):
        a = f"See your inventory in **Profile** → {LINKS['profile']}"
    if ctx.get("ach"):
        b = f"Show your badges → {LINKS['profile']}"
    return I18N["recommend"]["en" if lang == "en" else "tr"].format(one=a, two=b)


def H_debug(q, lang, ctx, user):
    return I18N["debug_hint"]["en" if lang == "en" else "tr"]


def H_time(q, lang, ctx, user):
    return ("The time is " if lang == "en" else "Şu an saat ") + _now().strftime("%H:%M")


def H_date(q, lang, ctx, user):
    return ("Today is " if lang == "en" else "Bugün tarih ") + _now().strftime("%d.%m.%Y")


def H_auth(q, lang, ctx, user, kind):
    if kind == "login":
        return ("Login: " if lang == "en" else "Giriş: ") + LINKS["login"]
    if kind == "signup":
        return ("Sign up: " if lang == "en" else "Kayıt: ") + LINKS["signup"]
    return (LINKS["profile"] if user else LINKS["login"])


# --------------------------------------------------------------------------------------
# Command router
# --------------------------------------------------------------------------------------

CMD_RX = re.compile(r"^\s*/([a-zA-Z]+)(?:\s+(.*))?$")


def _handle_command(cmd: str, arg: str, lang: str, ctx: dict, user: Optional[str]) -> Optional[str]:
    c = cmd.lower()
    a = (arg or "").strip()
    files_in = list(ctx.get("files_in") or [])
    # images (for gallery), non-images (for list)
    imgs = [f for f in files_in if _is_truthy(f.get("is_image")) or str(f.get("content_type", "")).startswith("image/")]
    nonimgs = [f for f in files_in if f not in imgs]

    if c in {"help", "h", "?"}:
        return _help(lang)
    if c in {"links"}:
        return _links(lang)
    if c in {"about", "bambi"}:
        return _about(lang)
    if c in {"inventory", "inv"}:
        return H_inv("", lang, ctx, user)
    if c in {"badges", "ach", "achievements"}:
        return H_ach("", lang, ctx, user)
    if c in {"reco", "suggest"}:
        return H_reco("", lang, ctx, user)
    if c in {"profile"}:
        return (_md_link("Profile", LINKS["profile"]) if user else _md_link("Login", LINKS["login"]))
    if c in {"login"}:
        return _md_link("Login", LINKS["login"])
    if c in {"signup", "register"}:
        return _md_link("Sign up", LINKS["signup"])
    if c in {"time"}:
        return H_time("", lang, ctx, user)
    if c in {"date"}:
        return H_date("", lang, ctx, user)
    if c in {"md"}:
        return _md_demo(lang)
    if c in {"theme"}:
        return _theme_hint(lang, a.lower())
    if c in {"summarize", "summary", "sum"}:
        if files_in:
            return _wrap_steps(_summarize_files(files_in, lang))
        else:
            return ("Attach a file first with the **📎** button." if lang == "en" else "Önce **📎** ile bir dosya ekle.")
    if c in {"extract"}:
        if files_in:
            ex = _extract_from_files(files_in)
            if lang == "en":
                parts = []
                if ex["emails"]: parts.append("**Emails**: " + _list_head(ex["emails"], 12))
                if ex["links"]: parts.append("**Links**: " + _list_head(ex["links"], 12))
                if ex["todos"]: parts.append("**TODOs**: " + _list_head(ex["todos"], 12))
                return _wrap_steps(*parts) if parts else "Nothing obvious found."
            else:
                parts = []
                if ex["emails"]: parts.append("**E-postalar**: " + _list_head(ex["emails"], 12))
                if ex["links"]: parts.append("**Linkler**: " + _list_head(ex["links"], 12))
                if ex["todos"]: parts.append("**TODO**: " + _list_head(ex["todos"], 12))
                return _wrap_steps(*parts) if parts else "Belirgin bir şey bulunamadı."
        else:
            return ("Attach a file first with the **📎** button." if lang == "en" else "Önce **📎** ile bir dosya ekle.")
    if c in {"todo"}:
        if files_in:
            ex = _extract_from_files(files_in)
            rows = ex["todos"][:10]
            if not rows:
                return ("No TODO lines found." if lang == "en" else "TODO satırı bulunamadı.")
            if lang == "en":
                return _wrap_steps("**TODOs found**", "\n".join(f"- {t}" for t in rows))
            else:
                return _wrap_steps("**Bulunan TODO’lar**", "\n".join(f"- {t}" for t in rows))
        else:
            return ("Attach a file first with the **📎** button." if lang == "en" else "Önce **📎** ile bir dosya ekle.")
    if c in {"stats"}:
        txt = a or ctx.get("message_text") or ""
        if not txt and files_in:
            for f in files_in:
                if f.get("text"):
                    txt = (txt + "\n\n" + f.get("text")).strip()
        if not txt:
            return ("Nothing to analyze." if lang == "en" else "Analiz edilecek içerik yok.")
        st = _simple_stats(txt)
        if lang == "en":
            return f"**Stats** · chars **{st['chars']}**, words **{st['words']}**, sentences **{st['sentences']}**, avg word **{st['avg_wlen']}**"
        else:
            return f"**İstatistik** · karakter **{st['chars']}**, kelime **{st['words']}**, cümle **{st['sentences']}**, ort. kelime **{st['avg_wlen']}**"
    return None


# --------------------------------------------------------------------------------------
# Rule-based intents (loose natural language)
# --------------------------------------------------------------------------------------

RULES: List[Tuple[re.Pattern, Any]] = [
    (words_rx(["merhaba", "selam", "hello", "hi", "hey", "günaydın", "good morning", "good evening"]), H_greet),
    (words_rx(["kimsin", "who are you", "sen kimsin", "hakkında", "about you"]), H_whoami),
    (words_rx(["bambicim", "site", "hakkında site", "about site"]), H_site),
    (words_rx(["envanter", "inventory", "nelerim var", "neler var"]), H_inv),
    (words_rx(["başarım", "rozet", "achievement", "achievements", "badges"]), H_ach),
    (words_rx(["öner", "öneri", "onerirsin", "recommend", "suggest"]), H_reco),
    (words_rx(["hata", "error", "problem", "sorun", "debug"]), H_debug),
    (words_rx(["saat", "time", "clock"]), H_time),
    (words_rx(["tarih", "date", "today"]), H_date),
    (words_rx(["giriş", "login", "sign in"]), lambda q, l, c, u: H_auth(q, l, c, u, "login")),
    (words_rx(["kayıt", "signup", "register", "sign up"]), lambda q, l, c, u: H_auth(q, l, c, u, "signup")),
    (words_rx(["profil", "profile"]),
     lambda q, l, c, u: (f"**Profile** → {LINKS['profile']}" if u else f"**Login** → {LINKS['login']}")),
    (words_rx(["oyun", "game", "bambi game"]), lambda q, l, c, u: f"**Bambi Game** → {LINKS['game']} 🎮"),
    (words_rx(["iletişim", "iletisim", "contact", "let's talk", "lets talk"]),
     lambda q, l, c, u: f"**Let’s talk** → {LINKS['contact']} 💌"),
    (words_rx(["work", "çalışma", "portfolio", "projects"]), lambda q, l, c, u: f"**Work** → {LINKS['work']} ✨"),
]


# --------------------------------------------------------------------------------------
# Main entry
# --------------------------------------------------------------------------------------

def reply_for(
        q: str,
        *,
        user_name: Optional[str] = None,
        lang: Optional[str] = None,
        context: Optional[dict] = None,
) -> str:
    """
    Create a Markdown reply string.
    context may include:
      - inv: list[{slug,name,emoji,qty}]
      - ach: list[{slug,name,emoji}]
      - files_in: list[{name,size,content_type,text?,url?,is_image?}]
      - urls_out / files_out are added by your view when returning JSON to the UI
      - message_text: original user message (for /stats)
    """
    ctx = dict(context or {})
    LL = (lang or _detect_lang(q or "")).lower()
    q_norm = _normalize(q or "")
    ctx["message_text"] = q

    # 1) Commands (start with '/')
    m = CMD_RX.match(q.strip())
    if m:
        cmd, arg = m.group(1), m.group(2) or ""
        out = _handle_command(cmd, arg, LL, ctx, user_name)
        if out:
            return out

    # 2) File-first flows — if files present and the message hints summarization
    files_in = list(ctx.get("files_in") or [])
    if files_in:
        if re.search(r"\b(summar|özet|extract|çıkar|todo|gözden|analy|istatistik)\b", q_norm):
            # delegate to summarize/extract commands
            if re.search(r"\b(extract|çıkar)\b", q_norm):
                return _handle_command("extract", "", LL, ctx, user_name) or ""
            if re.search(r"\b(todo)\b", q_norm):
                return _handle_command("todo", "", LL, ctx, user_name) or ""
            if re.search(r"\b(stat|istat)\b", q_norm):
                return _handle_command("stats", "", LL, ctx, user_name) or ""
            return _handle_command("summarize", "", LL, ctx, user_name) or ""

    # 3) FAQ quick answers
    faq = _faq_answer(q, LL)
    if faq:
        return faq

    # 4) Classic rule intents
    for rx, fn in RULES:
        if rx.search(q or "") or rx.search(q_norm):
            return fn(q, LL, ctx, user_name)

    # 5) Heuristic helpful nudge (inventory/achievements)
    parts: List[str] = []
    parts.append(f"{_hello(LL)} {_ask(LL)}")

    if LL == "en":
        parts.append(
            "Here are some quick things I can do:\n"
            "- " + _md_code("/links") + "  ·  site links\n"
                                        "- " + _md_code("/inventory") + " · items from the game\n"
                                                                        "- " + _md_code(
                "/summarize") + " · summarize your files (use the **📎**)\n"
                                "- " + _md_code("/md") + " · markdown demo"
        )
    else:
        parts.append(
            "Hızlı yapabildiklerim:\n"
            "- " + _md_code("/links") + "  ·  site linkleri\n"
                                        "- " + _md_code("/inventory") + " · oyundan eşyaların\n"
                                                                        "- " + _md_code(
                "/summarize") + " · dosyaları özetle (**📎** ile ekle)\n"
                                "- " + _md_code("/md") + " · markdown örneği"
        )

    # context-aware tease
    inv = list(ctx.get("inv") or [])
    ach = list(ctx.get("ach") or [])
    if inv:
        parts.append(H_inv("", LL, ctx, user_name))
    if ach:
        parts.append(H_ach("", LL, ctx, user_name))

    # Soft CTA
    if LL == "en":
        parts.append(f"_Or ping me with `{_md_code('/help')}` if you like menus._")
    else:
        parts.append(f"_İstersen `{_md_code('/help')}` yaz, küçük menümü açayım._")

    return _wrap_steps(*parts)
