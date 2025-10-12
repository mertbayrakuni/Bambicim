from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


# small helper for image previews in admin
def upload_to_assets(instance, filename):
    return f"editor/assets/{timezone.now():%Y/%m}/{filename}"


def upload_to_renders(instance, filename):
    return f"editor/renders/{timezone.now():%Y/%m}/{filename}"


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class EditorPreset(TimeStamped):
    """
    Stores sliders/filters and canvas options so you can offer one-click looks.
    """
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=200, blank=True)
    # keep this flexible — store anything your JS needs
    payload = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class EditorAsset(TimeStamped):
    """
    A source image a user uploaded (validated on upload view).
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    file = models.ImageField(upload_to=upload_to_assets)
    original_name = models.CharField(max_length=220, blank=True)
    bytes = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.original_name or self.file.name


class SavedEdit(TimeStamped):
    """
    A saved working file: references optional source asset and your editor state.
    """
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    title = models.CharField(max_length=140, default="Untitled")
    # frontend can POST the canvas state here (filters, elements, pan/zoom, etc.)
    state = models.JSONField(default=dict, blank=True)

    source = models.ForeignKey(EditorAsset, null=True, blank=True, on_delete=models.SET_NULL)

    # optional flattened info useful for listing
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    format = models.CharField(max_length=20, default="image/png")
    quality = models.PositiveIntegerField(default=92)

    # optional last exported image (if you choose to save one from frontend)
    last_render = models.ImageField(upload_to=upload_to_renders, blank=True, null=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.title} ({self.owner or 'anon'})"
