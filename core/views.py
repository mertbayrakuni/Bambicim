import json
import logging
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail, BadHeaderError
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from utils.github import get_recent_public_repos_cached
from .models import Item, Inventory, ChoiceLog

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
            send_mail(subject, body,
                      settings.DEFAULT_FROM_EMAIL,
                      ["mert@bambicim.com", "ipek@bambicim.com"],
                      fail_silently=False)
            messages.success(request, "Thanks! We’ll get back to you shortly.")
        except BadHeaderError:
            messages.error(request, "Invalid header found.")
        return redirect("home")
    return redirect("home")


ITEM_DEFS = {
    "pink-skirt": {"name": "Pink Skirt", "emoji": "🩷"},
    "lip-gloss": {"name": "Lip Gloss", "emoji": "💄"},
    "hair-bow": {"name": "Hair Bow", "emoji": "🎀"},
    "cat-ears": {"name": "Cat Ears", "emoji": "😼"},
    "combat-boots": {"name": "Combat Boots", "emoji": "🥾"},
}


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
    {
      "scene": "shop",
      "choice": "skirt",
      "gain": [{"slug": "pink-skirt", "qty": 1}, ...]
    }
    """
    data = json.loads(request.body or "{}")
    scene_id = data.get("scene") or ""
    choice_id = data.get("choice") or ""
    awards = data.get("gain") or []

    gained = []
    for award in awards:
        slug = (award or {}).get("slug")
        qty = int((award or {}).get("qty", 1))
        if not slug or qty <= 0:
            continue

        # create item on first sight (nice for prototyping)
        item, _ = Item.objects.get_or_create(
            slug=slug,
            defaults={"name": slug.replace("-", " ").title(), "emoji": "✨"},
        )

        inv, _ = Inventory.objects.get_or_create(
            user=request.user, item=item, defaults={"qty": 0}
        )
        Inventory.objects.filter(pk=inv.pk).update(qty=F("qty") + qty)
        inv.refresh_from_db()

        gained.append(
            {"slug": item.slug, "name": item.name, "qty": qty, "emoji": item.emoji}
        )

    if scene_id or choice_id:
        ChoiceLog.objects.create(user=request.user, scene=scene_id, choice=choice_id)

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
        {
            "slug": r.item.slug,
            "name": r.item.name,
            "qty": r.qty,
            "emoji": r.item.emoji,
        }
        for r in rows
    ]
    return JsonResponse({"items": items})
