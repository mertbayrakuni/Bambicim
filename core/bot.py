# core/bot.py  — persona + inventory/achievements aware

from __future__ import annotations

import datetime as dt
import random
import re

BASE = "https://bambicim.com"
LINKS = {
    "home": f"{BASE}/",
    "work": f"{BASE}/#work",
    "game": f"{BASE}/#game",
    "contact": f"{BASE}/#contact",
    "login": f"{BASE}/accounts/login/",
    "signup": f"{BASE}/accounts/signup/",
    "profile": f"{BASE}/profile/",
}


def _now(): return dt.datetime.now()


def _choose(xs): return random.choice(xs)


# ---- tiny language detection (TR/EN) ----
_TR_CHARS = "ıİşŞğĞçÇöÖüÜ"
_TR_HINTS = {"merhaba", "selam", "giriş", "kayıt", "oyun", "tema", "envanter", "profil", "iletisim", "iletişim", "hata"}
_EN_HINTS = {"hi", "hello", "login", "signup", "game", "theme", "inventory", "profile", "contact", "work", "error"}


def _normalize(s: str) -> str:
    tr = str.maketrans(
        {"İ": "i", "İ": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g", "Ç": "c", "ç": "c", "Ö": "o", "ö": "o",
         "Ü": "u", "ü": "u"})
    return (s or "").lower().translate(tr)


def _detect_lang(q: str) -> str:
    if any(c in (q or "") for c in _TR_CHARS): return "tr"
    qn = _normalize(q)
    if any(w in qn.split() for w in _TR_HINTS): return "tr"
    if any(w in qn.split() for w in _EN_HINTS): return "en"
    return "tr"


# ---- i18n ----
I18N = {
    "hello": {"tr": "Selam tatlım! 💖", "en": "Hi sweetie! 💖"},
    "ask_help": {"tr": "Bugün sana nasıl yardımcı olabilirim?", "en": "How can I help you today?"},
    "iam": {
        "tr": "Ben **Bambi** — pembe takıntılı mini yardımcı. Siteyi avucumun içi gibi biliyorum 💅",
        "en": "I’m **Bambi** — your pink-obsessed mini helper. I know this site by heart 💅",
    },
    "site_intro_tr": (
        "Burası **Bambicim** — notlar, deneyler ve *Bambi Game*. ✨\n"
        f"• Çalışmalar: {LINKS['work']}\n"
        f"• Bambi Game: {LINKS['game']} (kayıt olursan envanterin oluşur! 🎒)\n"
        f"• Let’s talk: {LINKS['contact']}\n"
        "Üst sağdaki renk noktalarıyla temayı değiştirebilirsin 🎀"
    ),
    "site_intro_en": (
        "This is **Bambicim** — notes, experiments and *Bambi Game*. ✨\n"
        f"• Selected Work: {LINKS['work']}\n"
        f"• Bambi Game: {LINKS['game']} (sign up to unlock inventory! 🎒)\n"
        f"• Let’s talk: {LINKS['contact']}\n"
        "Use the color dots top-right to switch theme 🎀"
    ),
    "inv_none": {"tr": "Envanter boş görünüyor. Biraz oyun? {game} 🎮",
                 "en": "Your inventory looks empty. Try the game? {game} 🎮"},
    "inv_some": {
        "tr": "Envanterinde **{n}** çeşit var: {list}. {tip}",
        "en": "You have **{n}** item types: {list}. {tip}",
    },
    "ach_none": {"tr": "Henüz rozet yok. İlkini kapmak için oyunda birkaç seçim dene ✨",
                 "en": "No badges yet — try a few choices in the game ✨"},
    "ach_some": {"tr": "Aferin! **{n}** rozetin var: {list}", "en": "Yay! You’ve got **{n}** badges: {list}"},
    "recommend": {
        "tr": "Önerim: {one} • {two}",
        "en": "My pick: {one} • {two}",
    },
    "debug_hint": {
        "tr": "Hata mı var? F9 ile debug panelini aç; HTTP durumunu görürsün. 403 görürsen `/api/chat` için CSRF muafiyeti gerekli.",
        "en": "Seeing an error? Press F9 to open the debug panel; you’ll see the HTTP status. If it’s 403, make `/api/chat` CSRF-exempt.",
    },
}


def _hello(lang): return I18N["hello"]["en" if lang == "en" else "tr"]


def _ask(lang):   return I18N["ask_help"]["en" if lang == "en" else "tr"]


def words_rx(ws): return re.compile(r"\b(?:%s)\b" % "|".join(re.escape(w) for w in ws), re.I)


# ---------- helpers for game context ----------
def _fmt_items(items, lang):
    # items: list of dicts/tuples -> try to render “emoji name × qty”
    out = []
    for r in items[:6]:
        slug = (r.get("slug") if isinstance(r, dict) else (r[0] if len(r) > 0 else "")) if r else ""
        name = (r.get("name") if isinstance(r, dict) else "") or slug
        emoji = (r.get("emoji") if isinstance(r, dict) else "")
        qty = (r.get("qty") if isinstance(r, dict) else (r[1] if len(r) > 1 else 1)) or 1
        label = f"{emoji} {name} × {qty}".strip()
        out.append(label)
    return ", ".join(out) if out else ""


def _inv_tip(lang, items):
    text = "Tema ‘pink’ ile daha tatlı görünür 💗" if lang != "en" else "Looks even cuter in the pink theme 💗"
    # tiny heuristics for fun
    s = " ".join((r.get("slug") if isinstance(r, dict) else r[0]) for r in items if r)
    if re.search(r"crown|ta[cç]|krali|queen", (s or ""), re.I):
        text = "Taç sende—kraliçe mod on 👑"
    elif re.search(r"heart|kalp", (s or ""), re.I):
        text = "Kalp toplamaya devam, aşk dolu ilerleme! 💖"
    elif re.search(r"star|yıldız", (s or ""), re.I):
        text = "Yıldızlar yol gösteriyor ⭐"
    return text


# ---------- intent handlers ----------
def H_greet(q, lang, ctx, user):
    sugg = _choose([
        f"Bambi Game: {LINKS['game']} 🎮",
        f"Work: {LINKS['work']} ✨",
        f"Let’s talk: {LINKS['contact']} 💌",
    ])
    return f"{_hello(lang)} {_ask(lang)}\n{I18N['iam'][lang]}\n{sugg}"


def H_whoami(q, lang, ctx, user):
    intro = I18N['site_intro_en' if lang == 'en' else 'site_intro_tr']
    return f"{I18N['iam'][lang]}\n{intro}"


def H_site(q, lang, ctx, user):
    return I18N['site_intro_en' if lang == 'en' else 'site_intro_tr']


def H_inv(q, lang, ctx, user):
    items = list(ctx.get("inv") or [])
    if not items:
        return I18N["inv_none"][lang].format(game=LINKS["game"])
    return I18N["inv_some"][lang].format(
        n=len(items), list=_fmt_items(items, lang), tip=_inv_tip(lang, items)
    )


def H_ach(q, lang, ctx, user):
    ach = list(ctx.get("ach") or [])
    if not ach:
        return I18N["ach_none"][lang]
    names = ", ".join(
        (f"{a.get('emoji', '')} {a.get('name', '')}".strip() if isinstance(a, dict) else str(a)) for a in ach[:8])
    return I18N["ach_some"][lang].format(n=len(ach), list=names)


def H_reco(q, lang, ctx, user):
    a = f"Game → {LINKS['game']}"
    b = f"Work → {LINKS['work']}"
    if ctx.get("inv"): a = f"Profilinde envanterin görünüyor → {LINKS['profile']}"
    if ctx.get("ach"): b = f"Rozetlerini göster → {LINKS['profile']}"
    return I18N["recommend"][lang].format(one=a, two=b)


def H_debug(q, lang, ctx, user):
    return I18N["debug_hint"][lang]


def H_time(q, lang, ctx, user): return ("Şu an saat " if lang != "en" else "The time is ") + _now().strftime("%H:%M")


def H_date(q, lang, ctx, user): return ("Bugün tarih " if lang != "en" else "Today is ") + _now().strftime("%d.%m.%Y")


def H_auth(q, lang, ctx, user, kind):
    if kind == "login": return ("Giriş: " if lang != "en" else "Login: ") + LINKS["login"]
    if kind == "signup": return ("Kayıt: " if lang != "en" else "Sign up: ") + LINKS["signup"]
    return LINKS["profile"] if user else (LINKS["login"])


# ---------- router ----------
RULES = [
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
     lambda q, l, c, u: (f"Profil: {LINKS['profile']}" if u else f"Login: {LINKS['login']}")),
    (words_rx(["oyun", "game", "bambi game"]), lambda q, l, c, u: f"Bambi Game: {LINKS['game']} 🎮"),
    (words_rx(["iletişim", "iletisim", "contact", "let's talk", "lets talk"]),
     lambda q, l, c, u: f"Let’s talk: {LINKS['contact']} 💌"),
    (words_rx(["work", "çalışma", "portfolio", "projects"]), lambda q, l, c, u: f"Work: {LINKS['work']} ✨"),
]


def reply_for(q: str, *, user_name: str | None = None, lang: str | None = None, context: dict | None = None) -> str:
    ctx = context or {}
    LL = lang or _detect_lang(q or "")
    qn = _normalize(q or "")
    for rx, fn in RULES:
        if rx.search(q or "") or rx.search(qn):
            return fn(q, LL, ctx, user_name)
    # fallback
    nudge = _choose([f"Contact → {LINKS['contact']} 💌", f"Game → {LINKS['game']} 🎮", f"Work → {LINKS['work']} ✨"])
    return f"{_hello(LL)} {_ask(LL)}\n{nudge}"
