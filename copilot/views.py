from __future__ import annotations

import json
import time
import uuid
from typing import Iterable

from django.db import transaction
from django.http import StreamingHttpResponse, JsonResponse, HttpRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from .models import Conversation, Message, Attachment
from .retrieval import search as rsearch


# ---------- helpers ----------
def _id() -> str:
    return uuid.uuid4().hex[:24]


def _json(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}


def _sse(event: str, data: dict | str) -> str:
    if not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n"


def _title_from(msg: str) -> str:
    msg = (msg or "").strip().split("\n", 1)[0]
    return (msg[:42] + "…") if len(msg) > 45 else msg


# ---------- endpoints ----------
@csrf_exempt
def upload_files(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    files = request.FILES.getlist("files") or []
    cid = request.POST.get("conversation_id") or _id()
    convo, _ = Conversation.objects.get_or_create(id=cid, defaults={"title": ""})
    out = []
    for f in files:
        att = Attachment(id=_id(), conversation=convo, file=f)
        att.set_meta_from_file()
        att.save()
        out.append({
            "id": att.id, "name": f.name, "url": att.file.url,
            "mime": att.mime, "size": att.size, "conversation_id": convo.id
        })
    return JsonResponse(out, safe=False)


@csrf_exempt
def search_api(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    payload = _json(request) if request.body else request.POST
    q = (payload.get("q") or "").strip()
    k = int(payload.get("k") or 6)
    return JsonResponse({"q": q, "results": rsearch(q, k)})


def _assistant_reply(user_text: str) -> tuple[str, list[dict]]:
    """
    Dumb-but-useful assistant: retrieve and craft a markdown reply with citations.
    You can swap this with your LLM later; the SSE plumbing stays the same.
    """
    cites = rsearch(user_text, 4)
    parts = []
    if "http" in user_text or "work" in user_text.lower() or "oyun" in user_text.lower():
        parts.append("**Hızlı düşünceler**")
        parts.append("- İçeriği taradım; aşağıdaki kaynaklar faydalı görünüyor.")
    else:
        parts.append("**Bambi Copilot** burada 💖 Kısa bir özet hazırlıyorum…")

    if cites:
        parts.append("\n**Kaynaklar**")
        for c in cites:
            title = c["title"] or c["url"]
            url = c["url"] or ""
            parts.append(f"- [{title}]({url}) — {c['snippet']}")
    else:
        parts.append("\nKaynak bulunamadı, daha fazla bağlam verir misin?")

    reply = "\n".join(parts)
    return reply, cites


@csrf_exempt
def chat_sse(request: HttpRequest):
    """
    SSE stream. Accepts JSON:
    {
      "conversation_id": "...",  # optional
      "message": "text",
      "file_ids": []
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    payload = _json(request) if request.body else request.POST
    user_text = (payload.get("message") or "").strip()
    cid = payload.get("conversation_id") or _id()

    if not user_text:
        return JsonResponse({"error": "empty message"}, status=400)

    # persist the user message
    with transaction.atomic():
        convo, created = Conversation.objects.get_or_create(id=cid, defaults={"title": _title_from(user_text)})
        if created and not convo.title:
            convo.title = _title_from(user_text)
            convo.save(update_fields=["title"])
        m_user = Message.objects.create(id=_id(), conversation=convo, role="user", content_md=user_text)

    # prepare assistant content
    full_reply, cites = _assistant_reply(user_text)

    def stream() -> Iterable[bytes]:
        # send a small greeting first (fast TTFB)
        yield _sse("delta", {"text": "Merhaba! Bir göz atıyorum…"}).encode("utf-8")
        time.sleep(0.15)

        # fake a tool call if we used retrieval
        if cites:
            yield _sse("tool", {"name": "retrieve", "status": "start", "args": {"q": user_text}}).encode("utf-8")
            time.sleep(0.10)
            yield _sse("tool", {"name": "retrieve", "status": "end", "result": cites}).encode("utf-8")

        # stream the markdown reply in chunks
        step = max(20, len(full_reply) // 12)
        for i in range(0, len(full_reply), step):
            yield _sse("delta", {"text": full_reply[i:i + step]}).encode("utf-8")
            time.sleep(0.04)

        # persist assistant message at the end
        Message.objects.create(
            id=_id(), conversation_id=cid, role="assistant",
            content_md=full_reply, meta={"citations": cites}
        )
        yield _sse("done", {"conversation_id": cid}).encode("utf-8")

    resp = StreamingHttpResponse(stream(), content_type="text/event-stream; charset=utf-8")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"  # nginx: prevent buffering
    return resp


def thread_get(request: HttpRequest, cid: str):
    convo = get_object_or_404(Conversation, id=cid)
    msgs = list(convo.messages.order_by("created_at").values("id", "role", "content_md", "created_at", "meta"))
    atts = list(convo.attachments.values("id", "mime", "size", "thumbnail_url", "file"))
    return JsonResponse({"id": convo.id, "title": convo.title, "messages": msgs, "attachments": atts})
