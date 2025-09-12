# core/views.py
import json
import logging
import os
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db.models import F
from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import strip_tags
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from utils.github import get_recent_public_repos_cached
from .models import Scene, Item, Inventory, ChoiceLog, Achievement, UserAchievement

log = logging.getLogger("app")


def home(request):
    user = os.environ.get("GITHUB_USERNAME", "mertbayrakuni")
    token = os.environ.get("GITHUB_TOKEN")  # optional
    repos = []

    try:
        repos = get_recent_public_repos_cached(user, token)
    except Exception:
        log.exception("GitHub repos fetch failed")
        repos = []  # fail silently; page still loads

    # parse pushed_at -> pushed_dt (aware datetime) for “timesince”
    for r in repos:
        dt = parse_datetime((r.get("pushed_at") or "").strip()) if isinstance(r, dict) else None
        r["pushed_dt"] = dt

    return render(request, "home.html", {"repos": repos})


CONTACT_RATE_LIMIT_SECONDS = 60  # adjust as you like
MAX_MESSAGE_LEN = 5000
MAX_URLS_IN_MESSAGE = 5  # crude spam limiter


def _client_ip(request):
    # Simple best-effort
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


@csrf_protect
def contact(request):
    # Render the same page as home on GET so the form shows correctly
    if request.method != "POST":
        return render(request, "home.html")

    # Honeypot: bots often fill hidden fields
    if request.POST.get("website", "").strip():
        # Silently pretend success (don’t help bots learn)
        messages.success(request, "Thanks! I’ll get back to you.")
        return redirect("home")

    name = (request.POST.get("name") or "").strip()
    email = (request.POST.get("email") or "").strip()
    raw_message = request.POST.get("message") or ""
    message = strip_tags(raw_message).strip()

    # Rate-limit by IP (check only; set after successful send)
    ip = _client_ip(request)
    rk = f"contact:rate:{ip}"
    if cache.get(rk):
        messages.error(
            request,
            "Please wait a bit before sending another message.",
            extra_tags="contact_error",
        )
        return redirect("home")

    # Basic validation
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
        # crude URL limiter to reduce spam payloads
        url_count = len(re.findall(r"https?://", message, flags=re.I))
        if url_count > MAX_URLS_IN_MESSAGE:
            errors.append("Too many links in the message.")

    if errors:
        for e in errors:
            messages.error(request, e, extra_tags="contact_error")
        return redirect("home")

    # Compose & send (use env-backed CONTACT_RECIPIENT and Reply-To)
    subject = f"[Bambicim] Contact from {name}"
    body = f"From: {name} <{email}>\nIP: {ip}\n\n{message}"
    try:
        email_msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[settings.CONTACT_RECIPIENT],
            reply_to=[email] if email else None,
        )
        email_msg.send(fail_silently=False)

        # set limiter only after a successful send
        cache.set(rk, 1, timeout=CONTACT_RATE_LIMIT_SECONDS)

        messages.success(request, "Thanks! I’ll get back to you.")
    except Exception:
        # Log the failure but keep the error generic
        log.exception("Contact email send failed")
        messages.error(
            request,
            "Sorry—couldn’t send your message right now.",
            extra_tags="contact_error",
        )

    return redirect("home")


ITEM_DEFS = {
    "pink-skirt": {"name": "Pink Skirt", "emoji": "💗"},
    "lip-gloss": {"name": "Lip Gloss", "emoji": "💄"},
    "hair-bow": {"name": "Hair Bow", "emoji": "🎀"},
    "hair-ribbon": {"name": "Hair Ribbon", "emoji": "🎀"},
    "cat-ears": {"name": "Cat Ears", "emoji": "🐱"},
    "combat-boots": {"name": "Combat Boots", "emoji": "🥾"},
}

BASE_ACHIEVEMENTS = [
    # slug, name, emoji, rule_type, rule_param, threshold, description
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
    """Create item on first sight with nice defaults."""
    defaults = ITEM_DEFS.get(
        slug, {"name": slug.replace("-", " ").title(), "emoji": "✨"}
    )
    obj, _ = Item.objects.get_or_create(slug=slug, defaults=defaults)
    return obj


@require_POST
@csrf_protect
@login_required
def game_choice(request):
    """
    Accepts JSON like either:
      {"scene":"shop","label":"Try skirt","gain":["pink-skirt","hair-bow"]}
    or:
      {"scene":"shop","label":"Try skirt","gain":[{"slug":"pink-skirt","qty":1}]}
    or:
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

        inv, _ = Inventory.objects.get_or_create(
            user=request.user, item=item, defaults={"qty": 0}
        )
        Inventory.objects.filter(pk=inv.pk).update(qty=F("qty") + qty)
        inv.refresh_from_db()

        gained.append(
            {"slug": item.slug, "name": item.name, "qty": qty, "emoji": item.emoji}
        )

    if scene_id or label:
        ChoiceLog.objects.create(user=request.user, scene=scene_id, choice=label)

    # check for achievements after inventory/choice updates
    new_ach = _award_achievements(request.user)

    return JsonResponse({"ok": True, "gained": gained, "achievements": new_ach})


@require_GET
@login_required
def game_inventory(request):
    rows = (
        Inventory.objects.filter(user=request.user)
        .select_related("item")
        .order_by("item__name")
    )
    items = [
        {"slug": r.item.slug, "name": r.item.name, "qty": r.qty, "emoji": r.item.emoji}
        for r in rows
    ]
    return JsonResponse({"items": items})


def _scene_key(scene):
    return scene.key


@require_GET
def game_scenes_json(request):
    start_scene = (
            Scene.objects.filter(is_start=True).first()
            or Scene.objects.order_by("key").first()
    )
    if not start_scene:
        raise Http404("No scenes found")

    scenes_qs = (
        Scene.objects.prefetch_related("choices__gains", "choices__next_scene")
        .order_by("key")
    )

    payload = {"start": _scene_key(start_scene), "scenes": {}}

    for sc in scenes_qs:
        node = {
            "id": sc.key,
            "title": sc.title or "",
            "text": sc.text or "",
            "choices": [],
        }
        for ch in sc.choices.all():  # related_name="choices"
            gains = [{"item": g.item.slug, "qty": g.qty} for g in ch.gains.all()]
            node["choices"].append(
                {
                    "text": ch.label,
                    "target": ch.next_scene.key if ch.next_scene else None,
                    "href": ch.href or None,
                    "gains": gains,
                }
            )
        payload["scenes"][sc.key] = node

    # defensive: if DB looks broken, force static JSON fallback
    total_choices = sum(len(n.get("choices", [])) for n in payload["scenes"].values())
    empty_labels = sum(
        1
        for n in payload["scenes"].values()
        for c in n.get("choices", [])
        if not (c.get("text") or c.get("label"))
    )
    if total_choices == 0 or empty_labels >= total_choices:
        return HttpResponse(status=404)

    return JsonResponse(payload)


def healthz(_request):
    return HttpResponse("ok", content_type="text/plain")


@require_POST
@login_required
def inventory_clear(request):
    Inventory.objects.filter(user=request.user).delete()
    messages.success(request, "Inventory cleared.")
    return redirect("profile")


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


def _award_achievements(user):
    """
    Evaluate simple rules against current inventory and recent scene.
    Returns list of newly unlocked achievements (dicts).
    """
    _ensure_achievements_seeded()

    # totals
    rows = Inventory.objects.filter(user=user).select_related("item")
    total_qty = sum(r.qty for r in rows)
    have = {r.item.slug for r in rows}

    unlocked = []

    for a in Achievement.objects.filter(is_active=True):
        # already owned?
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
