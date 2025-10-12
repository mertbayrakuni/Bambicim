from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import JsonResponse, HttpRequest, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from .models import EditorPreset, EditorAsset, SavedEdit


def editor(request: HttpRequest):
    return render(request, "editor/index.html")


@require_GET
def presets_json(request: HttpRequest):
    """List active presets so the UI can offer one-click looks."""
    data = [
        dict(id=p.id, name=p.name, description=p.description, payload=p.payload)
        for p in EditorPreset.objects.filter(is_active=True).order_by("name")
    ]
    return JsonResponse({"presets": data})


@login_required
@require_POST
def upload_asset(request: HttpRequest):
    """Upload a source image; returns asset id + url."""
    f = request.FILES.get("file")
    if not f:
        return HttpResponseBadRequest("no file")

    asset = EditorAsset.objects.create(
        owner=request.user,
        file=f,
        original_name=f.name,
        bytes=f.size or 0,
    )
    return JsonResponse(
        {"id": asset.id, "url": asset.file.url, "name": asset.original_name, "bytes": asset.bytes}
    )


@login_required
@require_POST
def save_edit(request: HttpRequest):
    """
    Create/update a SavedEdit (title + JSON state + optional source).
    Body: {id?, title, state, width, height, format, quality, source_id?}
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("invalid json")

    edit_id = payload.get("id")
    title = (payload.get("title") or "Untitled").strip()
    state = payload.get("state") or {}
    width = int(payload.get("width") or 0)
    height = int(payload.get("height") or 0)
    fmt = payload.get("format") or "image/png"
    quality = int(payload.get("quality") or 92)
    source_id = payload.get("source_id")

    source = None
    if source_id:
        source = get_object_or_404(EditorAsset, id=source_id, owner=request.user)

    if edit_id:
        edit = get_object_or_404(SavedEdit, id=edit_id, owner=request.user)
    else:
        edit = SavedEdit(owner=request.user)

    edit.title = title
    edit.state = state
    edit.width = width
    edit.height = height
    edit.format = fmt
    edit.quality = quality
    edit.source = source
    edit.save()

    return JsonResponse({"ok": True, "id": edit.id})


@login_required
@require_GET
def list_edits(request: HttpRequest):
    """Return the current user's recent edits (for a lightweight 'Open' dialog)."""
    items = SavedEdit.objects.filter(owner=request.user).order_by("-updated_at")[:50]
    data = [
        {
            "id": e.id,
            "title": e.title,
            "updated_at": e.updated_at.isoformat(),
            "size": [e.width, e.height],
            "format": e.format,
            "thumb": (e.last_render.url if e.last_render else None),
        }
        for e in items
    ]
    return JsonResponse({"items": data})


@login_required
@require_POST
def upload_render(request: HttpRequest):
    """
    Accept a base64 data URL or raw bytes of the exported image to store as last_render.
    Body: {id, data_url?} or multipart file field 'file'
    """
    edit_id = request.POST.get("id") or request.GET.get("id")
    if not edit_id:
        # allow JSON fallback
        try:
            payload = json.loads(request.body.decode("utf-8"))
            edit_id = payload.get("id")
            data_url = payload.get("data_url")
        except Exception:
            data_url = None
    else:
        data_url = request.POST.get("data_url")

    edit = get_object_or_404(SavedEdit, id=edit_id, owner=request.user)

    # handle file upload first
    file = request.FILES.get("file")
    if file:
        edit.last_render.save(file.name, file, save=True)
        return JsonResponse({"ok": True, "url": edit.last_render.url})

    # handle data URL (e.g., "data:image/png;base64,....")
    if data_url and data_url.startswith("data:"):
        header, b64 = data_url.split(",", 1)
        try:
            import base64

            blob = base64.b64decode(b64)
        except Exception:
            return HttpResponseBadRequest("bad data_url")

        ext = ".png" if "png" in header else ".jpg"
        name = f"render-{edit.id}{ext}"
        edit.last_render.save(name, ContentFile(blob), save=True)
        return JsonResponse({"ok": True, "url": edit.last_render.url})

    return HttpResponseBadRequest("no render provided")
