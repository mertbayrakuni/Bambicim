# core/bot.py
from __future__ import annotations

import datetime as dt
import random
import re
from typing import Callable, Pattern

Rule = tuple[Pattern[str], Callable[[re.Match[str]], str]]


def _now() -> dt.datetime:
    return dt.datetime.now()


def _greet(_: re.Match[str]) -> str:
    return "Selam tatlım! 💖 Bugün sana nasıl yardımcı olabilirim?"


def _time(_: re.Match[str]) -> str:
    return f"Şu an saat {_now().strftime('%H:%M')}."


def _date(_: re.Match[str]) -> str:
    return f"Bugün tarih {_now().strftime('%d.%m.%Y')}."


def _about(_: re.Match[str]) -> str:
    return ("Bambicim, Bambi’nin kişisel alanı: notlar, oyunlar (Bambi Game), "
            "hızlı prototipler ve pembe-güzel yazılımlar. ✨")


def _help(_: re.Match[str]) -> str:
    return ("Mini komutlar:\n"
            "• “zaman” / “saat” — şimdiki saat\n"
            "• “tarih” — bugünün tarihi\n"
            "• “oyun” — Bambi Game hakkında\n"
            "• “iletişim” — bana nasıl ulaşacağını anlatırım")


def _game(_: re.Match[str]) -> str:
    return ("Bambi Game, tarayıcıda minik bir hikâye oyunu. "
            "Seçeneklere tıklayıp eşya toplayabiliyorsun. "
            "Profiline girip envanterini görebilirsin. 🎮")


def _contact(_: re.Match[str]) -> str:
    return ("En hızlı yol: sayfadaki ‘Let’s talk’ bölümünden formu doldur "
            "veya ipek@bambicim.com’a e-posta gönder. 💌")


def _work(_: re.Match[str]) -> str:
    return "“Work” bölümünde seçili işler ve deneylerimi listeliyorum. 🔧"


def _polite(_: re.Match[str]) -> str:
    return random.choice([
        "Anladım tatlım. Biraz daha açar mısın? 💞",
        "Güzel soru! Birlikte çözelim mi? 💖",
        "Hmm… Biraz daha detay verir misin?"
    ])


# Regex → handler
RULES: list[Rule] = [
    (re.compile(r"^(merhaba|selam|hey|hello|hi)\b", re.I), _greet),
    (re.compile(r"\b(saat|time|zaman)\b", re.I), _time),
    (re.compile(r"\b(tarih|date)\b", re.I), _date),
    (re.compile(r"\b(hakkında|about)\b", re.I), _about),
    (re.compile(r"\b(help|yard[iı]m)\b", re.I), _help),
    (re.compile(r"\b(oyun|bambi ?game)\b", re.I), _game),
    (re.compile(r"\b(ilet[ii]ş[ii]m|contact|reach)\b", re.I), _contact),
    (re.compile(r"\b(work|çalışma|projeler)\b", re.I), _work),
]


def reply_for(q: str, *, user_name: str | None = None) -> str:
    q = (q or "").strip()
    if not q:
        return "Merhaba! Ben Bambi 💖 Bugün sana nasıl yardımcı olabilirim?"
    for rx, fn in RULES:
        m = rx.search(q)
        if m:
            return fn(m)
    # small polite fallback
    return _polite(None)
