from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import Category, Tag, Post, PostImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1


@admin.action(description="Publish now")
def publish_now(modeladmin, request, queryset):
    queryset.update(status="published", publish_at=timezone.now())


@admin.action(description="Mark as draft")
def mark_draft(modeladmin, request, queryset):
    queryset.update(status="draft")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "publish_at", "category", "featured", "thumb")
    list_filter = ("status", "featured", "category", "publish_at", "tags")
    search_fields = ("title", "excerpt", "content")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "publish_at"
    autocomplete_fields = ("category", "tags")
    readonly_fields = ("created_at", "updated_at", "reading_time")
    inlines = [PostImageInline]
    actions = [publish_now, mark_draft]

    fieldsets = (
        (None, {
            "fields": ("title", "slug", "author", "category", "tags", "featured", "status", "publish_at")
        }),
        ("Content", {
            "fields": ("excerpt", "content", "cover_image")
        }),
        ("SEO", {
            "fields": ("seo_title", "seo_description", "canonical_url")
        }),
        ("Meta", {
            "fields": ("reading_time", "created_at", "updated_at")
        }),
    )

    def thumb(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" style="height:40px;border-radius:6px;" />', obj.cover_image.url)
        return "-"

    thumb.short_description = "Cover"
