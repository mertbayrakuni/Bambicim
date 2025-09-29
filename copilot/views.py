# copilot/views.py
from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Iterable, Dict, Any, List

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import StreamingHttpResponse, JsonResponse, HttpRequest
from django.utils.cache import patch_cache_control
from django.utils.text import get_valid_filename
from django.views.decorators.csrf import csrf_exempt

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore


# --- minimal helpers ----------------------------------------------------------
def _id() -> str: return uuid.uuid4().hex


def _is_tr(s: str) -> bool:
    return bool(re.search(r"[ıİşŞğĞçÇöÖüÜ]", s or ""))


def _safe_name(name: str) -> str:
    base, ext = os.path.splitext(get_valid_filename(name or "file"))
    return f"{base[:40]}{ext.lower()}"


def _save_uploads(files) -> List[Dict[str, Any]]:
    saved = []
    for f in files:
        path = f"chat_uploads/{_id()}-{_safe_name(f.name)}"
        saved_path = default_storage.save(path, f)
        url = default_storage.url(saved_path)
        saved.append({
            "name": f.name, "url": url,
            "size": getattr(f, "size", 0),
            "content_type": getattr(f, "content_type", "") or ""
        })
    return saved


# --- site links / persona (mirror core) --------------------------------------
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

MODEL = getattr(settings, "BMB_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = getattr(settings, "OPENAI_API_KEY", "")

PERSONA = (getattr(settings, "BMB_SYS_PERSONA", "") or f"""
You are **Bambi** — playful, flirty, helpful assistant of bambicim.com.
Tone: warm, concise, emoji-friendly. Bilingual (TR/EN).
Be an expert on the site and always give exact links when relevant.
Links: Home {LINKS['home']} · Work {LINKS['work']} · Game {LINKS['game']} · Contact {LINKS['contact']}
Auth: Login {LINKS['login']} · Signup {LINKS['signup']} · Profile {LINKS['profile']}
Policies: Privacy {LINKS['privacy']} · Terms {LINKS['terms']}
""").strip()


def _msgs_for(q: str, files_meta: List[Dict[str, Any]] | None = None) -> List[Dict[str, str]]:
    msgs: List[Dict[str, str]] = [{"role": "system", "content": PERSONA}]
    u = (q or "Hello").strip()
    if files_meta:
        desc = "\n".join(f"- {f.get('name')} · {f.get('content_type')} · {f.get('size', 0)} bytes"
                         for f in files_meta)
        u = (u + f"\n\n(Attached files)\n{desc}").strip()
    msgs.append({"role": "user", "content": u})
    return msgs


def _client() -> OpenAI | None:
    if not OPENAI_API_KEY or OpenAI is None:
        return None
    return OpenAI(api_key=OPENAI_API_KEY)


def _sse(event: str, data: Dict[str, Any] | str) -> bytes:
    if not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n".encode("utf-8")


# --- /api/copilot/upload (optional files before chat) ------------------------
@csrf_exempt
def upload(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    convo = request.POST.get("conversation_id") or _id()
    files = request.FILES.getlist("files") or []
    meta = _save_uploads(files)
    # return the convo id & file metas (no DB needed)
    out = [{"conversation_id": convo, **m} for m in meta] or [{"conversation_id": convo}]
    return JsonResponse(out, safe=False)


# --- /api/copilot/chat (SSE streaming) ---------------------------------------
@csrf_exempt
def chat(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        payload = json.loads((request.body or b"").decode("utf-8"))
    except Exception:
        payload = {}
    q = (payload.get("message") or "").strip()
    conv_id = payload.get("conversation_id") or _id()
    files_meta: List[Dict[str, Any]] = []  # if you want to stitch uploads, pass meta here

    if not q:
        return JsonResponse({"error": "empty message"}, status=400)

    msgs = _msgs_for(q, files_meta)
    cli = _client()

    def stream() -> Iterable[bytes]:
        # small warm-up hint so the UI shows life immediately
        yield _sse("delta", {"text": "🪄 thinking…"})
        time.sleep(0.08)

        if not cli:
            # offline fallback: short canned answer
            lang = "tr" if _is_tr(q) else "en"
            text = ("Şu an çevrimdışıyım; bu arada şunlara bakabilirsin: "
                    f"Home {LINKS['home']} · Work {LINKS['work']} · Game {LINKS['game']} · Contact {LINKS['contact']}"
                    ) if lang == "tr" else \
                ("I’m offline; meanwhile check: "
                 f"Home {LINKS['home']} · Work {LINKS['work']} · Game {LINKS['game']} · Contact {LINKS['contact']}")
            # typewriter-ish chunks
            step = max(24, len(text) // 12)
            for i in range(0, len(text), step):
                yield _sse("delta", {"text": text[i:i + step]})
                time.sleep(0.03)
            yield _sse("done", {"conversation_id": conv_id})
            return

        try:
            stream = cli.responses.stream(
                model=MODEL,
                input=[{"role": m["role"], "content": m["content"]} for m in msgs],
                max_output_tokens=800,
            )
            for event in stream:
                if event.type == "response.output_text.delta":
                    yield _sse("delta", {"text": event.delta})
                elif event.type == "response.completed":
                    break
            yield _sse("done", {"conversation_id": conv_id})
        except Exception as e:
            yield _sse("delta", {"text": f"\n\n_(error: {e})_"})
            yield _sse("done", {"conversation_id": conv_id})

    resp = StreamingHttpResponse(stream(), content_type="text/event-stream; charset=utf-8")
    patch_cache_control(resp, no_cache=True)
    resp["X-Accel-Buffering"] = "no"
    return resp
