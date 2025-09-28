from __future__ import annotations

import hashlib
import mimetypes

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


def _now():
    return timezone.now()


def _upload_to(instance, filename: str) -> str:
    return f"copilot/{instance.conversation_id}/{filename}"


class Conversation(models.Model):
    id = models.CharField(primary_key=True, max_length=40, editable=False)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(default=_now)
    updated_at = models.DateTimeField(default=_now)

    def save(self, *a, **kw):
        self.updated_at = _now()
        super().save(*a, **kw)

    def __str__(self):
        return self.title or f"Conversation {self.id}"


class Message(models.Model):
    ROLE_CHOICES = [("user", "user"), ("assistant", "assistant"), ("tool", "tool")]
    id = models.CharField(primary_key=True, max_length=40, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=12, choices=ROLE_CHOICES)
    content_md = models.TextField(blank=True, default="")
    tokens_in = models.IntegerField(default=0)
    tokens_out = models.IntegerField(default=0)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=_now)

    def __str__(self):
        return f"{self.role}: {self.content_md[:40]}"


class Attachment(models.Model):
    id = models.CharField(primary_key=True, max_length=40, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="attachments")
    message = models.ForeignKey(Message, null=True, blank=True, on_delete=models.SET_NULL, related_name="attachments")
    file = models.FileField(upload_to=_upload_to)
    mime = models.CharField(max_length=120, blank=True, default="")
    size = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    thumbnail_url = models.URLField(blank=True, default="")
    created_at = models.DateTimeField(default=_now)

    def set_meta_from_file(self):
        self.size = getattr(self.file, "size", 0) or 0
        self.mime = self.mime or (self.file.file and getattr(self.file.file, "content_type", "")) \
                    or mimetypes.guess_type(self.file.name)[0] or ""
        h = hashlib.sha256()
        for chunk in self.file.chunks():
            h.update(chunk)
        self.sha256 = h.hexdigest()


class Doc(models.Model):
    KIND = [("page", "page"), ("note", "note"), ("code", "code")]
    id = models.CharField(primary_key=True, max_length=40, editable=False)
    kind = models.CharField(max_length=12, choices=KIND, default="page")
    slug = models.CharField(max_length=200, blank=True, default="")
    title = models.CharField(max_length=300, blank=True, default="")
    url = models.CharField(max_length=500, blank=True, default="")
    text = models.TextField()
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=_now)
    updated_at = models.DateTimeField(default=_now)

    def save(self, *a, **kw):
        self.updated_at = _now()
        super().save(*a, **kw)

    def __str__(self): return self.title or self.slug or self.url or self.id


# copilot/models.py (append)

class Paragraph(models.Model):
    """
    A small chunk of text from a Doc (used for retrieval).
    Keep it tiny (1–3 sentences) for better recall.
    """
    doc = models.ForeignKey("copilot.Doc", on_delete=models.CASCADE, related_name="paragraphs")
    order = models.PositiveIntegerField(default=0, db_index=True)
    text = models.TextField()
    # denormalized for fast render (optional but handy)
    title = models.CharField(max_length=300, blank=True, default="")
    url = models.URLField(max_length=800, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["doc", "order"]),
        ]

    def __str__(self):
        return f"{self.doc_id}#{self.order}"
