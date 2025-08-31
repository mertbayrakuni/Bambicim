import json
import logging
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail, BadHeaderError
from django.db.models import F
from django.http import JsonResponse, Http404, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from utils.github import get_recent_public_repos_cached
from .models import Scene, Item, Inventory, ChoiceLog

log = logging.getLogger("app")


def home(request):
    user = os.environ.get("GITHUB_USERNAME", "mertbayrakuni")
    token = os.environ.get("GITHUB_TOKEN")  # optional
    repos = []
    try:
        repos = get_recent_public_repos_cached(user, token)
    except Exception:
        repos = []  # fail silently; page still loads
    return render(request, "home.html", {"repos": repos})


def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        msg = request.POST.get("message", "").strip()
        if not (name and email and msg):
            messages.error(request, "Please fill in all fields.")
            return redirect("home")
        subject = f"New lead — Bambicim: {name}"
        body = f"From: {name} <{email}>\n\n{msg}"
        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                ["mert@bambicim.com", "ipek@bambicim.com"],
                fail_silently=False,
            )
            messages.success(request, "Thanks! We’ll get back to you shortly.")
        except BadHeaderError:
            messages.error(request, "Invalid header found.")
        return redirect("home")
    return redirect("home")


ITEM_DEFS = {
    "pink-skirt": {"name": "Pink Skirt", "emoji": "💗"},
    "lip-gloss": {"name": "Lip Gloss", "emoji": "💄"},
    "hair-bow": {"name": "Hair Bow", "emoji": "🎀"},
    "hair-ribbon": {"name": "Hair Ribbon", "emoji": "🎀"},
    "cat-ears": {"name": "Cat Ears", "emoji": "🐱"},
    "combat-boots": {"name": "Combat Boots", "emoji": "🥾"},
}


def _ensure_item(slug: str) -> Item:
    """Create item on first sight with nice defaults."""
    defaults = ITEM_DEFS.get(slug, {"name": slug.replace("-", " ").title(), "emoji": "✨"})
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

        gained.append({"slug": item.slug, "name": item.name, "qty": qty, "emoji": item.emoji})

    if scene_id or label:
        ChoiceLog.objects.create(user=request.user, scene=scene_id, choice=label)

    return JsonResponse({"ok": True, "gained": gained})


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

    scenes_qs = Scene.objects.prefetch_related(
        "choices__gains", "choices__next_scene"
    ).order_by("key")

    payload = {"start": _scene_key(start_scene), "scenes": {}}

    for sc in scenes_qs:
        node = {"id": sc.key, "title": sc.title or "", "text": sc.text or "", "choices": []}
        for ch in sc.choices.all():  # related_name="choices"
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
