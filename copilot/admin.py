# copilot/admin.py
from django.contrib import admin

from .models import Conversation, Message, Attachment, Doc


# ── Inlines for a dashboard feel ───────────────────────────────────────────────
class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("role", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("role", "created_at")


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ("mime", "size", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("mime", "size", "created_at")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "user", "msg_count", "attachment_count", "updated_at")
    search_fields = ("id", "title", "user__username")
    date_hierarchy = "updated_at"
    inlines = [MessageInline, AttachmentInline]
    ordering = ("-updated_at",)

    @admin.display(description="#Msgs")
    def msg_count(self, obj):
        return obj.messages.count()

    @admin.display(description="#Files")
    def attachment_count(self, obj):
        return obj.attachments.count()


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "created_at", "short_preview")
    list_filter = ("role",)
    search_fields = ("id", "content_md", "conversation__id")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    @admin.display(description="Preview")
    def short_preview(self, obj):
        text = (obj.content_md or "")[:120]
        return (text + "…") if len(text) == 120 else text


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "mime", "size", "created_at")
    search_fields = ("id", "file", "conversation__id", "sha256")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(Doc)
class DocAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "title", "slug", "url", "updated_at")
    search_fields = ("title", "slug", "url", "text")
    ordering = ("-updated_at",)

try:
    from .models import APICall
except Exception:
    APICall = None

if APICall:
    @admin.register(APICall)
    class APICallAdmin(admin.ModelAdmin):
        list_display = ("created_at", "user", "conversation", "provider", "model", "tokens_in", "tokens_out",
                        "cost_usd", "success")
        list_filter = ("provider", "model", "success", "http_status")
        date_hierarchy = "created_at"
        search_fields = ("user__username", "conversation__id", "model")
        readonly_fields = ("created_at",)
