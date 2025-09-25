from __future__ import annotations

import datetime as dt
import random
import re
from typing import Callable, Pattern

# ====== Links & little helpers ======
BASE = "https://bambicim.com"
LINKS = {
    "home": f"{BASE}/",
    "work": f"{BASE}/#work",
    "game": f"{BASE}/#game",
    "contact": f"{BASE}/#contact",
    "login": f"{BASE}/accounts/login/",
    "signup": f"{BASE}/accounts/signup/",
    "profile": f"{BASE}/profile/",  # Shown only if logged in
}


def _now() -> dt.datetime: return dt.datetime.now()


def _choose(items): return random.choice(items)


def _hello_line(user_name: str | None) -> str:
    if user_name:
        return f"Selam {user_name}! 💖"
    return "Selam tatlım! 💖"


def _theme_tip() -> str:
    return "Üst sağdaki minik renk noktalarıyla temayı değiştirebilirsin—pembe, sıcak, beyaz… hepsi Bambi! 🎀"


def _cta_login_or_signup(user_name: str | None) -> str:
    if user_name:
        return f"Profilin: {LINKS['profile']}  •  Çalışmalar: {LINKS['work']}"
    return f"Giriş: {LINKS['login']}  •  Kayıt: {LINKS['signup']}"


def _site_intro(user_name: str | None) -> str:
    lines = [
        _hello_line(user_name),
        "Burası **Bambicim**: notlar, deneyler ve *Bambi Game*’li pembe bir oyun alanı. ✨",
        f"• Çalışmalar: {LINKS['work']}",
        f"• Bambi Game: {LINKS['game']} (kayıt olursan envanterin oluşur! 🎒)",
        f"• Let’s talk (iletişim): {LINKS['contact']}",
        _theme_tip(),
        _cta_login_or_signup(user_name),
    ]
    return "\n".join(lines)


# ====== Handlers ======
Rule = tuple[Pattern[str], Callable[[re.Match[str], str | None], str]]


def _greet(_: re.Match[str], user_name: str | None) -> str:
    # cute greeting + one rotating suggestion
    suggest = _choose([
        f"Bambi Game’i denedin mi? {LINKS['game']} (kayıt olup envanterini açabilirsin 💼)",
        f"Çalışmalarıma göz atmak ister misin? {LINKS['work']} ✨",
        f"Bana yazmak istersen: {LINKS['contact']} 💌",
        _theme_tip(),
    ])
    return f"{_hello_line(user_name)} Bugün sana nasıl yardımcı olabilirim?\n{suggest}"


def _time(_: re.Match[str], __: str | None) -> str:
    return f"Şu an saat {_now().strftime('%H:%M')}."


def _date(_: re.Match[str], __: str | None) -> str:
    return f"Bugün tarih {_now().strftime('%d.%m.%Y')}."


def _about(_: re.Match[str], user_name: str | None) -> str:
    return _site_intro(user_name)


def _help(_: re.Match[str], user_name: str | None) -> str:
    return (
        "Mini komutlar:\n"
        "• “zaman / saat” — şimdiki saat\n"
        "• “tarih” — bugünün tarihi\n"
        "• “oyun / bambi game” — oyun bilgisi ve linki\n"
        "• “iletişim / let’s talk / contact” — mesaj gönderme\n"
        "• “tema / renk / dark / pink” — tema ipuçları\n"
        "• “kayıt / üye ol / signup”, “giriş / login” — hesap işlemleri\n"
        "• “profil / envanter” — (giriş yaptıysan) profilin"
    )


def _game(_: re.Match[str], user_name: str | None) -> str:
    start = f"Bambi Game burada: {LINKS['game']} 🎮"
    inv = "Kayıt olursan envanterin oluşur ve ilerlemen saklanır."
    auth = _cta_login_or_signup(user_name)
    return f"{start}\n{inv}\n{auth}"


def _contact(_: re.Match[str], __: str | None) -> str:
    return f"En hızlı yol: ‘Let’s talk’ bölümü {LINKS['contact']} ya da ipek@bambicim.com 💌"


def _work(_: re.Match[str], __: str | None) -> str:
    return f"Seçili işlerim ve deneylerim burada: {LINKS['work']} ✨"


def _auth_signup(_: re.Match[str], __: str | None) -> str:
    return f"Üyelik açmak için buradayız tatlım: {LINKS['signup']}  (30 sn sürmez 😉)"


def _auth_login(_: re.Match[str], __: str | None) -> str:
    return f"Giriş için: {LINKS['login']}  •  Parolanı unutursan oradan sıfırlayabilirsin."


def _profile(_: re.Match[str], user_name: str | None) -> str:
    if user_name:
        return f"Profiline gidebilirsin: {LINKS['profile']}  •  Oyunda envanterin de oradan görünür. 🎒"
    return f"Profil ve envanter için önce giriş yapmalısın tatlım: {LINKS['login']}"


def _theme(_: re.Match[str], __: str | None) -> str:
    return (
        f"{_theme_tip()} 💅\n"
        "Bir tıkla pembe/sıcak/beyaz temalar arasında gezebilirsin; yazılar ve butonlar anında uyum sağlar."
    )


def _polite(_: re.Match[str] | None, __: str | None) -> str:
    return _choose([
        "Anladım tatlım. Biraz daha açar mısın? 💞",
        "Güzel soru! Birlikte çözelim mi? 💖",
        "Hmm… Biraz daha detay verir misin?",
        _theme_tip(),
    ])


# ====== Regex → handler table ======
RULES: list[Rule] = [
    (re.compile(r"^(merhaba|selam|hey|hello|hi)\b", re.I), _greet),
    (re.compile(r"\b(saat|time|zaman)\b", re.I), _time),
    (re.compile(r"\b(tarih|date)\b", re.I), _date),

    # site intro / about
    (re.compile(r"\b(bambicim|site|hakkında|nedir|about)\b", re.I), _about),

    # help
    (re.compile(r"\b(help|yard[iı]m)\b", re.I), _help),

    # core sections
    (re.compile(r"\b(oyun|bambi ?game)\b", re.I), _game),
    (re.compile(r"\b(ilet[iı]şim|iletisim|contact|let'?s ?talk)\b", re.I), _contact),
    (re.compile(r"\b(work|çalışma|projeler|works?)\b", re.I), _work),

    # auth & profile
    (re.compile(r"\b(kay[iı]t|kaydol|üye ol|signup)\b", re.I), _auth_signup),
    (re.compile(r"\b(giri[sş]|login|sign ?in)\b", re.I), _auth_login),
    (re.compile(r"\b(profil|envanter|inventory)\b", re.I), _profile),

    # theme
    (re.compile(r"\b(tema|theme|renk|dark|pink|hot|white)\b", re.I), _theme),
]


def reply_for(q: str, *, user_name: str | None = None) -> str:
    q = (q or "").strip()
    if not q:
        return _site_intro(user_name)

    for rx, fn in RULES:
        m = rx.search(q)
        if m:
            return fn(m, user_name)

    # default: cute nudge + one useful link
    nudge = _choose([
        f"Bana yazmak istersen: {LINKS['contact']} 💌",
        f"Bambi Game: {LINKS['game']} (kayıt olursan envanterin oluşur) 🎒",
        f"Çalışmalar: {LINKS['work']} ✨",
        _theme_tip(),
    ])
    return f"{_polite(None, user_name)}\n{nudge}"
