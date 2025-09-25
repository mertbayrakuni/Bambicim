from __future__ import annotations

import datetime as dt
import random
import re
from typing import Callable, Pattern

# ====== Links & helpers ======
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


def _now() -> dt.datetime:
    return dt.datetime.now()


def _choose(items):  # cute randomizer for variety
    return random.choice(items)


# --- very small language detector (tr / en) ---
_TR_CHARS = "ıİşŞğĞçÇöÖüÜ"
_TR_HINTS = {"merhaba", "selam", "giriş", "kayıt", "oyun", "tema", "envanter", "profil", "iletisim", "iletişim"}
_EN_HINTS = {"hi", "hello", "login", "signup", "game", "theme", "inventory", "profile", "contact", "work"}


def _normalize(s: str) -> str:
    # lowercase + simple TR→ASCII map for fuzzy matching
    tr_map = str.maketrans({
        "İ": "i", "İ": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g", "Ç": "c", "ç": "c", "Ö": "o", "ö": "o",
        "Ü": "u", "ü": "u"
    })
    return s.lower().translate(tr_map)


def _detect_lang(q: str) -> str:
    if any(ch in q for ch in _TR_CHARS):
        return "tr"
    qn = _normalize(q)
    if any(w in qn.split() for w in _TR_HINTS):
        return "tr"
    if any(w in qn.split() for w in _EN_HINTS):
        return "en"
    # default to TR (your site tone). Change to "en" if you prefer.
    return "tr"


# ====== i18n strings ======
I18N = {
    "hello": {
        "tr": "Selam tatlım! 💖",
        "en": "Hi sweetie! 💖",
    },
    "ask_help": {
        "tr": "Bugün sana nasıl yardımcı olabilirim?",
        "en": "How can I help you today?",
    },
    "site_intro": {
        "tr": (
            "Burası **Bambicim** — notlar, deneyler ve *Bambi Game*’li pembe bir oyun alanı. ✨\n"
            "• Çalışmalar: {work}\n"
            "• Bambi Game: {game} (kayıt olursan envanterin oluşur! 🎒)\n"
            "• Let’s talk: {contact}\n"
            "{theme_tip}\n"
            "{auth_cta}"
        ),
        "en": (
            "Welcome to **Bambicim** — notes, experiments and a pink playground with *Bambi Game*. ✨\n"
            "• Selected Work: {work}\n"
            "• Bambi Game: {game} (sign up to unlock your inventory! 🎒)\n"
            "• Let’s talk: {contact}\n"
            "{theme_tip}\n"
            "{auth_cta}"
        ),
    },
    "theme_tip": {
        "tr": "Üst sağdaki minik renk noktalarıyla temayı değiştirebilirsin—pembe, sıcak, beyaz… hepsi Bambi! 🎀",
        "en": "Use the tiny color dots at the top-right to switch theme—pink, hot, white… all Bambi! 🎀",
    },
    "auth_cta_signed": {
        "tr": "Profilin: {profile}  •  Çalışmalar: {work}",
        "en": "Your profile: {profile}  •  Work: {work}",
    },
    "auth_cta_guest": {
        "tr": "Giriş: {login}  •  Kayıt: {signup}",
        "en": "Login: {login}  •  Sign up: {signup}",
    },
    "help": {
        "tr": (
            "Mini komutlar:\n"
            "• “zaman / saat” — şimdiki saat\n"
            "• “tarih” — bugünün tarihi\n"
            "• “oyun / bambi game” — oyun bilgisi ve linki\n"
            "• “iletişim / let’s talk / contact” — mesaj gönderme\n"
            "• “tema / renk / dark / pink” — tema ipuçları\n"
            "• “kayıt / üye ol / signup”, “giriş / login” — hesap işlemleri\n"
            "• “profil / envanter” — (giriş yaptıysan) profilin"
        ),
        "en": (
            "Mini commands:\n"
            "• “time / clock” — current time\n"
            "• “date / today” — today’s date\n"
            "• “game / bambi game” — game info & link\n"
            "• “contact / let’s talk” — message Bambi\n"
            "• “theme / color / dark / pink” — theme tips\n"
            "• “signup / register”, “login / sign in” — account\n"
            "• “profile / inventory” — your profile (when logged in)"
        ),
    },
    "game": {
        "tr": "Bambi Game burada: {game} 🎮\nKayıt olursan envanterin oluşur ve ilerlemen saklanır.\n{auth_cta}",
        "en": "Bambi Game is here: {game} 🎮\nSign up to get an inventory and save progress.\n{auth_cta}",
    },
    "contact": {
        "tr": "En hızlı yol: ‘Let’s talk’ {contact} ya da ipek@bambicim.com 💌",
        "en": "Fastest way: ‘Let’s talk’ {contact} or email ipek@bambicim.com 💌",
    },
    "work": {
        "tr": "Seçili işlerim ve deneylerim burada: {work} ✨",
        "en": "My selected work & experiments: {work} ✨",
    },
    "signup": {
        "tr": "Üyelik açmak için: {signup} (30 sn sürmez 😉)",
        "en": "Create an account here: {signup} (takes ~30s 😉)",
    },
    "login": {
        "tr": "Giriş için: {login}  •  Parolanı unutursan oradan sıfırlayabilirsin.",
        "en": "Login here: {login} • You can reset your password there too.",
    },
    "profile_signed": {
        "tr": "Profilin: {profile} • Oyunda envanterin de oradan görünür. 🎒",
        "en": "Your profile: {profile} • Your game inventory is shown there too. 🎒",
    },
    "profile_guest": {
        "tr": "Profil ve envanter için önce giriş yapmalısın tatlım: {login}",
        "en": "To view profile & inventory, please log in first: {login}",
    },
    "time": {
        "tr": "Şu an saat {t}.",
        "en": "The time is {t}.",
    },
    "date": {
        "tr": "Bugün tarih {d}.",
        "en": "Today is {d}.",
    },
    "polite": {
        "tr": [
            "Anladım tatlım. Biraz daha açar mısın? 💞",
            "Güzel soru! Birlikte çözelim mi? 💖",
            "Hmm… Biraz daha detay verir misin?",
        ],
        "en": [
            "Got it, sweetie. Could you share a bit more? 💞",
            "Nice question! Shall we solve it together? 💖",
            "Hmm… can you give me a little more detail?",
        ],
    },
}


def _t(key: str, lang: str) -> str | list[str]:
    return I18N[key]["tr" if lang != "en" else "en"]


def _theme_tip(lang: str) -> str:
    return _t("theme_tip", lang)


def _auth_cta(lang: str, user_name: str | None) -> str:
    tmpl = _t("auth_cta_signed", lang) if user_name else _t("auth_cta_guest", lang)
    return tmpl.format(**LINKS)


def _site_intro(lang: str, user_name: str | None) -> str:
    return _t("site_intro", lang).format(
        work=LINKS["work"], game=LINKS["game"], contact=LINKS["contact"],
        theme_tip=_theme_tip(lang), auth_cta=_auth_cta(lang, user_name)
    )


# ====== Handlers (bilingual) ======
Rule = tuple[Pattern[str], Callable[[re.Match[str], str, str | None, str, str], str]]


# signature: (match, q_raw, user_name, lang, q_norm) -> reply

def H_greet(m, q, user, lang, qn):
    suggest = _choose([
        (_t("game", lang).split("\n")[0] + "").format(game=LINKS["game"], auth_cta=""),
        _t("work", lang).format(work=LINKS["work"]),
        _t("contact", lang).format(contact=LINKS["contact"]),
        _theme_tip(lang),
    ])
    hello = _t("hello", lang)
    ask = _t("ask_help", lang)
    return f"{hello} {ask}\n{suggest}"


def H_time(m, q, user, lang, qn):
    return _t("time", lang).format(t=_now().strftime("%H:%M"))


def H_date(m, q, user, lang, qn):
    return _t("date", lang).format(d=_now().strftime("%d.%m.%Y"))


def H_about(m, q, user, lang, qn):
    return _site_intro(lang, user)


def H_help(m, q, user, lang, qn):
    return _t("help", lang)


def H_game(m, q, user, lang, qn):
    return _t("game", lang).format(game=LINKS["game"], auth_cta=_auth_cta(lang, user))


def H_contact(m, q, user, lang, qn):
    return _t("contact", lang).format(contact=LINKS["contact"])


def H_work(m, q, user, lang, qn):
    return _t("work", lang).format(work=LINKS["work"])


def H_signup(m, q, user, lang, qn):
    return _t("signup", lang).format(signup=LINKS["signup"])


def H_login(m, q, user, lang, qn):
    return _t("login", lang).format(login=LINKS["login"])


def H_profile(m, q, user, lang, qn):
    if user:
        return _t("profile_signed", lang).format(profile=LINKS["profile"])
    return _t("profile_guest", lang).format(login=LINKS["login"])


def H_theme(m, q, user, lang, qn):
    return _theme_tip(lang) + (" 💅" if lang == "en" else " 💅")


def H_fallback(q, user, lang):
    polite = _choose(_t("polite", lang))
    nudge = _choose([
        _t("contact", lang).format(contact=LINKS["contact"]),
        _t("game", lang).format(game=LINKS["game"], auth_cta=""),
        _t("work", lang).format(work=LINKS["work"]),
        _theme_tip(lang),
    ])
    return f"{polite}\n{nudge}"


# ====== Intent regex (TR + EN synonyms) ======
def words_rx(words: list[str]) -> Pattern[str]:
    # join into \b(?:w1|w2|...)\b and allow spaces/optional apostrophes
    patt = r"|".join(re.escape(w) for w in words)
    return re.compile(rf"\b(?:{patt})\b", re.I)


RX = {
    "greet": words_rx(["merhaba", "selam", "hello", "hi", "hey", "günaydın", "good morning", "good evening"]),
    "time": words_rx(["saat", "zaman", "time", "clock"]),
    "date": words_rx(["tarih", "date", "today"]),
    "about": words_rx(["bambicim", "site", "nedir", "about", "what is", "who are you"]),
    "help": words_rx(["yardım", "yardim", "help", "commands", "how to use"]),
    "game": words_rx(["oyun", "bambi game", "game", "play", "oyna"]),
    "contact": words_rx(
        ["iletisim", "iletişim", "contact", "let's talk", "lets talk", "message", "reach", "email", "e-mail"]),
    "work": words_rx(["work", "works", "çalışma", "calisma", "projeler", "projects", "portfolio"]),
    "signup": words_rx(["kayıt", "kayit", "kaydol", "üye ol", "signup", "sign up", "register", "create account"]),
    "login": words_rx(["giriş", "giris", "login", "log in", "sign in"]),
    "profile": words_rx(["profil", "profile", "envanter", "inventory", "account", "my account"]),
    "theme": words_rx(["tema", "theme", "renk", "color", "dark", "pink", "hot", "white", "switch theme", "mode"]),
}

RULES: list[tuple[str, Pattern[str], Callable]] = [
    ("greet", RX["greet"], H_greet),
    ("time", RX["time"], H_time),
    ("date", RX["date"], H_date),
    ("about", RX["about"], H_about),
    ("help", RX["help"], H_help),
    ("game", RX["game"], H_game),
    ("contact", RX["contact"], H_contact),
    ("work", RX["work"], H_work),
    ("signup", RX["signup"], H_signup),
    ("login", RX["login"], H_login),
    ("profile", RX["profile"], H_profile),
    ("theme", RX["theme"], H_theme),
]


# ====== Public API ======
def reply_for(q: str, *, user_name: str | None = None, lang: str | None = None) -> str:
    """
    Stateless, site-aware, bilingual bot.
    - Auto-detects language when `lang` is None ("tr" default fallback).
    - user_name is used to customize auth CTAs & profile replies.
    """
    q_raw = (q or "").strip()
    if not q_raw:
        LL = lang or _detect_lang(q_raw)
        return _site_intro(LL, user_name)

    LL = lang or _detect_lang(q_raw)
    q_norm = _normalize(q_raw)

    # try each rule on raw OR normalized (to catch diacritics-agnostic matches)
    for _name, rx, handler in RULES:
        m = rx.search(q_raw) or rx.search(q_norm)
        if m:
            return handler(m, q_raw, user_name, LL, q_norm)

    # nothing matched → cute fallback
    return H_fallback(q_raw, user_name, LL)
