from django.contrib import admin
from django.utils.html import format_html

from .models import EditorPreset, EditorAsset, SavedEdit


@admin.register(EditorPreset)
class EditorPresetAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "description", "is_active")}),
        ("Payload (JSON)", {"fields": ("payload",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(EditorAsset)
class EditorAssetAdmin(admin.ModelAdmin):
    list_display = ("thumb", "original_name", "owner", "bytes", "created_at")
    search_fields = ("original_name", "file")
    list_filter = ("owner",)
    readonly_fields = ("created_at", "updated_at", "bytes")

    def thumb(self, obj):
        if not obj.file:
            return "-"
        return format_html('<img src="{}" style="height:40px;border-radius:6px" />', obj.file.url)


@admin.register(SavedEdit)
class SavedEditAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "size_fmt", "format", "quality", "updated_at", "render_thumb")
    list_filter = ("format", "owner")
    search_fields = ("title",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("title", "owner", "source")}),
        ("Editor State", {"fields": ("state",)}),
        ("Flattened", {"fields": ("width", "height", "format", "quality")}),
        ("Last Render", {"fields": ("last_render",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def size_fmt(self, obj):
        return f"{obj.width}×{obj.height}"

    def render_thumb(self, obj):
        if not obj.last_render:
            return "-"
        return format_html('<img src="{}" style="height:40px;border-radius:6px" />', obj.last_render.url)
