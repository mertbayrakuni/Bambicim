# blog/admin.py
from django.contrib import admin
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.html import format_html

from .models import Category, Tag, Post, PostImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1
    fields = ("image", "caption", "order", "preview")
    readonly_fields = ("preview",)
    ordering = ("order",)

    @admin.display(description="Preview")
    def preview(self, obj):
        if getattr(obj, "image", None):
            return format_html('<img src="{}" style="height:60px;border-radius:6px" />', obj.image.url)
        return "—"


@admin.action(description="Publish now")
def publish_now(modeladmin, request, queryset):
    queryset.update(status="published", publish_at=timezone.now())


@admin.action(description="Mark as draft")
def mark_draft(modeladmin, request, queryset):
    queryset.update(status="draft")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("thumb", "title", "status", "publish_at", "category", "featured")
    list_display_links = ("thumb", "title")
    list_filter = ("status", "featured", "category", "publish_at", "tags")
    search_fields = ("title", "excerpt", "content")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "publish_at"
    autocomplete_fields = ("category", "tags")
    readonly_fields = ("created_at", "updated_at", "reading_time")
    inlines = [PostImageInline]
    actions = [publish_now, mark_draft]
    save_on_top = True
    list_select_related = ("category", "author")
    ordering = ("-publish_at", "-created_at")

    fieldsets = (
        (None, {"fields": ("title", "slug", "author", "category", "tags", "featured", "status", "publish_at")}),
        ("Content", {"fields": ("excerpt", "content", "cover_image")}),
        ("SEO", {"fields": ("seo_title", "seo_description", "canonical_url")}),
        ("Meta", {"fields": ("reading_time", "created_at", "updated_at")}),
    )

    @admin.display(description="Cover")
    def thumb(self, obj):
        if obj.cover_image:
            # Relative /media/... URL is fine inside admin
            return format_html('<img src="{}" style="height:40px;border-radius:6px" />', obj.cover_image.url)
        return "—"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Avoid N+1 for tags and category on list page
        return qs.select_related("category", "author").prefetch_related(
            Prefetch("tags", queryset=Tag.objects.only("id", "name"))
        )
