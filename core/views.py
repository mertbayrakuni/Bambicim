# core/views.py
from __future__ import annotations

import json
import logging
import os
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple
from typing import Iterable
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db.models import F
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import strip_tags
from django.utils.text import get_valid_filename
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET, require_POST

from blog.models import Post
from portfolio.models import Project
# keep your app models & art helpers
from .art import generate_pixel_art, run_in_thread, _prompt_for
from .models import Scene, Item, Inventory, ChoiceLog, Achievement, UserAchievement, SceneArt

log = logging.getLogger("app")


# -----------------------------------------------------------------------------
# Home (GitHub recent repos — safe import)
# -----------------------------------------------------------------------------
def home(request):
    user = os.environ.get("GITHUB_USERNAME", "mertbayrakuni")
    token = os.environ.get("GITHUB_TOKEN")  # optional
    repos = []
    try:
        # lazy import so missing utils/github doesn’t crash boot
        from utils.github import get_recent_public_repos_cached
        repos = get_recent_public_repos_cached(user, token) or []
    except Exception:
        log.exception("GitHub repos fetch failed")
        repos = []

    # parse pushed_at -> pushed_dt (aware datetime) for “timesince” in template
    for r in repos:
        dt = parse_datetime((r.get("pushed_at") or "").strip()) if isinstance(r, dict) else None
        r["pushed_dt"] = dt

    return render(request, "home.html", {"repos": repos})


# -----------------------------------------------------------------------------
# Contact form (rate-limited + email)
# -----------------------------------------------------------------------------
CONTACT_RATE_LIMIT_SECONDS = 60
MAX_MESSAGE_LEN = 5000
MAX_URLS_IN_MESSAGE = 5


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


@csrf_protect
def contact(request):
    if request.method != "POST":
        return render(request, "home.html")

    # Honeypot
    if request.POST.get("website", "").strip():
        messages.success(request, "Thanks! I’ll get back to you.")
        return redirect("home")

    name = (request.POST.get("name") or "").strip()
    email = (request.POST.get("email") or "").strip()
    raw_message = request.POST.get("message") or ""
    message = strip_tags(raw_message).strip()

    # Rate-limit by IP
    ip = _client_ip(request)
    rk = f"contact:rate:{ip}"
    if cache.get(rk):
        messages.error(request, "Please wait a bit before sending another message.", extra_tags="contact_error")
        return redirect("home")

    # Validation
    errors = []
    if not name:
        errors.append("Name is required.")
    if not email:
        errors.append("Email is required.")
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors.append("Please enter a valid email address.")
    if not message:
        errors.append("Message is required.")
    elif len(message) > MAX_MESSAGE_LEN:
        errors.append("Message is too long.")
    else:
        if len(re.findall(r"https?://", message, flags=re.I)) > MAX_URLS_IN_MESSAGE:
            errors.append("Too many links in the message.")

    if errors:
        for e in errors:
            messages.error(request, e, extra_tags="contact_error")
        return redirect("home")

    # Send email
    subject = f"[Bambicim] Contact from {name}"
    body = f"From: {name} <{email}>\nIP: {ip}\n\n{message}"
    try:
        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[settings.CONTACT_RECIPIENT],
            reply_to=[email] if email else None,
        )
        msg.send(fail_silently=False)
        cache.set(rk, 1, timeout=CONTACT_RATE_LIMIT_SECONDS)
        messages.success(request, "Thanks! I’ll get back to you.")
    except Exception:
        log.exception("Contact email send failed")
        messages.error(request, "Sorry—couldn’t send your message right now.", extra_tags="contact_error")
    return redirect("home")


# -----------------------------------------------------------------------------
# Game: inventory / achievements / scenes
# -----------------------------------------------------------------------------
ITEM_DEFS = {
    "pink-skirt": {"name": "Pink Skirt", "emoji": "💗"},
    "lip-gloss": {"name": "Lip Gloss", "emoji": "💄"},
    "hair-bow": {"name": "Hair Bow", "emoji": "🎀"},
    "hair-ribbon": {"name": "Hair Ribbon", "emoji": "🎀"},
    "cat-ears": {"name": "Cat Ears", "emoji": "🐱"},
    "combat-boots": {"name": "Combat Boots", "emoji": "🥾"},
}

BASE_ACHIEVEMENTS = [
    ("first-pick", "First Pick", "🪄", Achievement.RULE_COLLECT_COUNT, "", 1, "Collect your first item."),
    ("pink-queen", "Pink Queen", "💗", Achievement.RULE_COLLECT_ITEM, "pink-skirt", 1, "Own the pink skirt."),
    ("accessorized", "Accessorized", "🎀", Achievement.RULE_COLLECT_COUNT, "", 3, "Collect 3 total items."),
    ("hoarder", "Hoarder", "🧺", Achievement.RULE_COLLECT_COUNT, "", 5, "Collect 5 total items."),
]


def _ensure_achievements_seeded():
    for slug, name, emoji, rtype, rparam, thr, desc in BASE_ACHIEVEMENTS:
        Achievement.objects.get_or_create(
            slug=slug,
            defaults=dict(
                name=name, emoji=emoji, rule_type=rtype,
                rule_param=rparam, threshold=thr, description=desc, is_active=True
            ),
        )


def _ensure_item(slug: str) -> Item:
    defaults = ITEM_DEFS.get(slug, {"name": slug.replace("-", " ").title(), "emoji": "✨"})
    obj, _ = Item.objects.get_or_create(slug=slug, defaults=defaults)
    return obj


@require_POST
@csrf_protect
@login_required
def game_choice(request):
    """
    Accepts JSON like:
      {"scene":"shop","label":"Try skirt","gain":["pink-skirt","hair-bow"]}
      {"scene":"shop","label":"Try skirt","gain":[{"slug":"pink-skirt","qty":1}]}
      {"scene":"shop","label":"Try skirt","gain":[{"item":"pink-skirt","qty":1}]}
    """
    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "bad-json"}, status=400)

    scene_id = (data.get("scene") or "").strip()
    label = (data.get("label") or data.get("choice") or "").strip()
    awards = data.get("gain") or data.get("gains") or []

    gained = []
    for award in awards:
        if isinstance(award, str):
            slug, qty = award.strip(), 1
        else:
            slug = ((award or {}).get("item") or (award or {}).get("slug") or "").strip()
            qty = int((award or {}).get("qty", 1) or 1)
        if not slug or qty <= 0:
            continue

        item = _ensure_item(slug)
        inv, _ = Inventory.objects.get_or_create(user=request.user, item=item, defaults={"qty": 0})
        Inventory.objects.filter(pk=inv.pk).update(qty=F("qty") + qty)
        inv.refresh_from_db()
        gained.append({"slug": item.slug, "name": item.name, "qty": qty, "emoji": item.emoji})

    if scene_id or label:
        ChoiceLog.objects.create(user=request.user, scene=scene_id, choice=label)

    new_ach = _award_achievements(request.user)
    return JsonResponse({"ok": True, "gained": gained, "achievements": new_ach})


@require_GET
@login_required
def game_inventory(request):
    rows = Inventory.objects.filter(user=request.user).select_related("item").order_by("item__name")
    items = [{"slug": r.item.slug, "name": r.item.name, "qty": r.qty, "emoji": r.item.emoji} for r in rows]
    return JsonResponse({"items": items})


def _scene_key(scene: Scene) -> str:
    return scene.key


@require_GET
def game_scenes_json(request):
    start_scene = Scene.objects.filter(is_start=True).first() or Scene.objects.order_by("key").first()
    if not start_scene:
        raise Http404("No scenes found")

    scenes_qs = Scene.objects.prefetch_related("choices__gains", "choices__next_scene").order_by("key")

    payload = {"start": _scene_key(start_scene), "scenes": {}}
    for sc in scenes_qs:
        node = {"id": sc.key, "title": sc.title or "", "text": sc.text or "", "choices": []}
        for ch in sc.choices.all():
            gains = [{"item": g.item.slug, "qty": g.qty} for g in ch.gains.all()]
            node["choices"].append({
                "text": ch.label,
                "target": ch.next_scene.key if ch.next_scene else None,
                "href": ch.href or None,
                "gains": gains,
            })
        payload["scenes"][sc.key] = node

    # defensive: if DB looks broken, force static JSON fallback
    total_choices = sum(len(n.get("choices", [])) for n in payload["scenes"].values())
    empty_labels = sum(
        1 for n in payload["scenes"].values() for c in n.get("choices", []) if not (c.get("text") or c.get("label"))
    )
    if total_choices == 0 or empty_labels >= total_choices:
        return HttpResponse(status=404)

    return JsonResponse(payload)


# -----------------------------------------------------------------------------
# Pixel art generation (async, idempotent)
# -----------------------------------------------------------------------------
def _scene_for_prompt(scene_key: str) -> Tuple[str, str]:
    sc = Scene.objects.filter(key=scene_key).first()
    if sc:
        return sc.title or scene_key, sc.text or ""
    return scene_key, ""


def _ensure_scene_art(scene_key: str):
    obj, _ = SceneArt.objects.get_or_create(key=scene_key, defaults={"prompt": "", "status": "pending"})
    if obj.status == "ready":
        return

    title, text = _scene_for_prompt(scene_key)
    prompt = _prompt_for(scene_key, title, text)
    obj.prompt = prompt
    obj.status = "pending"
    obj.save(update_fields=["prompt", "status", "updated_at"])

    def worker():
        try:
            data = generate_pixel_art(prompt)
            SceneArt.objects.filter(pk=obj.pk).update(
                image_webp=data, status="ready", updated_at=timezone.now()
            )
        except Exception:
            SceneArt.objects.filter(pk=obj.pk).update(status="failed", updated_at=timezone.now())

    run_in_thread(worker)


@require_GET
@login_required
def scene_art_ensure(request, scene_key: str):
    _ensure_scene_art(scene_key)
    row = SceneArt.objects.filter(key=scene_key).first()
    return JsonResponse({"ok": True, "status": row.status if row else "pending"})


@require_GET
@cache_control(public=True, max_age=86400)
def scene_art_image(request, scene_key: str):
    row = SceneArt.objects.filter(key=scene_key, status="ready").only("image_webp").first()
    if not row or not row.image_webp:
        return HttpResponse(status=404)
    return HttpResponse(bytes(row.image_webp), content_type="image/webp")


@require_GET
def scene_art_ensure_all(_request):
    # Prefer DB scenes; fallback to static JSON file
    keys = list(Scene.objects.values_list("key", flat=True))
    if not keys:
        try:
            p = os.path.join(settings.BASE_DIR, "core", "static", "game", "scenes.json")
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            keys = list((data.get("scenes") or {}).keys())
        except Exception:
            keys = []
    for k in keys:
        _ensure_scene_art(k)
    return JsonResponse({"ok": True, "count": len(keys), "keys": keys})


# -----------------------------------------------------------------------------
# Inventory utilities & achievements logic
# -----------------------------------------------------------------------------
def _award_achievements(user):
    _ensure_achievements_seeded()
    rows = Inventory.objects.filter(user=user).select_related("item")
    total_qty = sum(r.qty for r in rows)
    have = {r.item.slug for r in rows}

    unlocked = []
    for a in Achievement.objects.filter(is_active=True):
        if UserAchievement.objects.filter(user=user, achievement=a).exists():
            continue
        ok = False
        if a.rule_type == Achievement.RULE_COLLECT_ITEM:
            ok = a.rule_param in have
        elif a.rule_type == Achievement.RULE_COLLECT_COUNT:
            ok = total_qty >= max(1, a.threshold)
        elif a.rule_type == Achievement.RULE_REACH_SCENE:
            ok = ChoiceLog.objects.filter(user=user, scene=a.rule_param).exists()
        if ok:
            UserAchievement.objects.create(user=user, achievement=a, achieved_at=timezone.now())
            unlocked.append({"slug": a.slug, "name": a.name, "emoji": a.emoji})
    return unlocked


@require_GET
@login_required
def game_achievements(request):
    _ensure_achievements_seeded()
    rows = (
        UserAchievement.objects.filter(user=request.user)
        .select_related("achievement")
        .order_by("achieved_at")
    )
    data = [
        {
            "slug": r.achievement.slug,
            "name": r.achievement.name,
            "emoji": r.achievement.emoji,
            "at": r.achieved_at.isoformat(),
        }
        for r in rows
    ]
    return JsonResponse({"items": data})


@require_POST
@login_required
def inventory_clear(request):
    Inventory.objects.filter(user=request.user).delete()
    messages.success(request, "Inventory cleared.")
    return redirect("profile")


# -----------------------------------------------------------------------------
# Healthcheck
# -----------------------------------------------------------------------------
def healthz(_request):
    return HttpResponse("ok", content_type="text/plain")


# -----------------------------------------------------------------------------
# OpenAI (v1) chat endpoint — NO copilot/retrieval imports
# -----------------------------------------------------------------------------
# Small site links for grounding
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

# Persona (can override with BMB_SYS_PERSONA in settings/.env)
PERSONA = (getattr(settings, "BMB_SYS_PERSONA", "") or f"""
You are **Bambi** — playful, flirty, helpful assistant of bambicim.com.
Tone: warm, concise, emoji-friendly. Bilingual (TR/EN) based on the user.
Be an expert on the site and always include exact links when relevant.
Links: Home {LINKS['home']} · Work {LINKS['work']} · Game {LINKS['game']} · Contact {LINKS['contact']}
Auth: Login {LINKS['login']} · Signup {LINKS['signup']} · Profile {LINKS['profile']}
Policies: Privacy {LINKS['privacy']} · Terms {LINKS['terms']}
""").strip()

QA_BOOST = [
    {"q": "what is bambicim", "a": f"Bambicim is a lab of notes, experiments and the **Bambi Game** → {LINKS['home']}"},
    {"q": "bambi game",
     "a": f"Play the **Bambi Game** → {LINKS['game']}. Choices set flags; inventory & badges show in your Profile."},
    {"q": "contact", "a": f"Use the **Let’s talk** form → {LINKS['contact']}"},
    {"q": "login", "a": f"Login → {LINKS['login']} · Sign up → {LINKS['signup']}"},
    {"q": "portfolio", "a": f"Selected Work lives on the homepage → {LINKS['work']}"},
    {"q": "privacy", "a": f"Privacy policy → {LINKS['privacy']}"},
    {"q": "terms", "a": f"Terms of Service → {LINKS['terms']}"},
    {"q": "profile inventory badges",
     "a": f"Your **Profile** shows inventory/badges after playing the game → {LINKS['profile']}"},
]


def _qa_context(user_text: str) -> str:
    t = (user_text or "").lower()
    hits = []
    for row in QA_BOOST:
        if any(w in t for w in row["q"].split()):
            hits.append("- " + row["a"])
    return ("Helpful site snippets:\n" + "\n".join(hits[:4])) if hits else ""


def _is_tr(s: str) -> bool:
    return bool(re.search(r"[ıİşŞğĞçÇöÖüÜ]", s or ""))


def _safe_name(name: str) -> str:
    base, ext = os.path.splitext(get_valid_filename(name or "file"))
    return f"{base[:40]}{ext.lower()}"


def _save_uploads(files) -> List[Dict[str, Any]]:
    saved = []
    for f in files:
        path = f"chat_uploads/{uuid4().hex}-{_safe_name(f.name)}"
        saved_path = default_storage.save(path, f)
        url = default_storage.url(saved_path)
        saved.append({
            "name": f.name,
            "url": url,
            "size": getattr(f, "size", 0),
            "content_type": getattr(f, "content_type", "") or ""
        })
    return saved


def _messages_for(user_text: str, files_meta: List[Dict[str, Any]] | None = None) -> List[Dict[str, str]]:
    msgs: List[Dict[str, str]] = [{"role": "system", "content": PERSONA}]
    ctx = _qa_context(user_text)
    if ctx:
        msgs.append({"role": "system", "content": ctx})
    u = (user_text or "Hello").strip()
    if files_meta:
        desc = "\n".join(f"- {f.get('name')} · {f.get('content_type')} · {f.get('size', 0)} bytes" for f in files_meta)
        u = (u + f"\n\n(Attached files)\n{desc}").strip()
    msgs.append({"role": "user", "content": u})
    return msgs


def _openai_client():
    try:
        from openai import OpenAI
    except Exception:
        return None
    api_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


@csrf_exempt
def api_chat(request):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)

    try:
        q = ""
        files_meta: List[Dict[str, Any]] = []
        # multipart uploads supported
        if request.content_type and "multipart/form-data" in request.content_type:
            q = (request.POST.get("q") or "").strip()
            uploads = request.FILES.getlist("files")
            if uploads:
                files_meta = _save_uploads(uploads)
        else:
            data = json.loads(request.body or "{}")
            q = (data.get("q") or "").strip()

        msgs = _messages_for(q, files_meta)
        reply = None

        cli = _openai_client()
        if cli:
            try:
                model = getattr(settings, "BMB_MODEL", "gpt-4o-mini")
                resp = cli.responses.create(
                    model=model,
                    input=[{"role": m["role"], "content": m["content"]} for m in msgs],
                    max_output_tokens=700,
                )
                reply = (resp.output_text or "").strip() or None
            except Exception as e:
                log.exception("OpenAI chat error: %s", e)

        if not reply:
            # offline fallback
            lang = "tr" if _is_tr(q) else "en"
            reply = (
                "Şu an çevrimdışıyım; bu arada şunlara bakabilirsin: "
                f"Home {LINKS['home']} · Work {LINKS['work']} · Game {LINKS['game']} · Contact {LINKS['contact']}"
            ) if lang == "tr" else (
                "I’m in offline mode; meanwhile check: "
                f"Home {LINKS['home']} · Work {LINKS['work']} · Game {LINKS['game']} · Contact {LINKS['contact']}"
            )

        # UI goodies
        image_urls = [f["url"] for f in files_meta if (f.get("content_type") or "").startswith("image/")]

        return JsonResponse({"reply": reply, "urls": image_urls, "files": files_meta})
    except Exception as e:
        log.exception("api_chat error")
        return JsonResponse({"error": "bot_error", "detail": str(e)}, status=500)


def _tokens(q: str) -> list[str]:
    # words with len>=3, lowercase
    return [t.lower() for t in re.findall(r"\w+", q or "") if len(t) >= 3]


def _qs_posts():
    # prefer your published() manager if present
    mgr = Post.objects
    return getattr(mgr, "published", lambda: mgr.all())()


def _match_qobj(tokens: Iterable[str]) -> Q:
    q = Q()
    for t in tokens:
        q |= (
                Q(title__icontains=t) |
                Q(excerpt__icontains=t) |
                Q(body__icontains=t) |
                Q(body_html__icontains=t)
        )
    return q


def _as_text(obj) -> str:
    title = strip_tags(getattr(obj, "title", "") or "")
    excerpt = strip_tags(getattr(obj, "excerpt", "") or "")
    body = strip_tags(getattr(obj, "body", "") or getattr(obj, "body_html", "") or "")
    return f"{title}\n{excerpt}\n{body}"


def _score(text: str, tokens: list[str]) -> float:
    # simple hybrid: token hits + fuzzy ratio
    text_l = text.lower()
    hits = sum(text_l.count(t) for t in tokens)
    fuzz = SequenceMatcher(None, " ".join(tokens), text_l[:3000]).ratio()
    return hits * 2.0 + fuzz  # weight token matches higher


def search(request):
    q = (request.GET.get("q") or "").strip()
    tokens = _tokens(q)
    posts = projects = []
    if q:
        # Primary filter (fast)
        base_posts = _qs_posts().filter(_match_qobj(tokens)).distinct()[:50]
        base_projects = Project.objects.filter(_match_qobj(tokens)).distinct()[:50]

        # Score & sort (fuzzy)
        posts = sorted(
            base_posts,
            key=lambda p: _score(_as_text(p), tokens),
            reverse=True,
        )[:20]
        projects = sorted(
            base_projects,
            key=lambda pr: _score(_as_text(pr), tokens),
            reverse=True,
        )[:10]

    return render(request, "search.html", {
        "q": q,
        "posts": posts,
        "projects": projects,
        "tokens": tokens,
    })
