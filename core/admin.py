# core/admin.py
import base64

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Sum
from django.utils.html import format_html

from .models import (
    Item, Inventory, GameSession, ChoiceLog,
    Scene, Choice, ChoiceGain,
    Achievement, UserAchievement, SceneArt,
)
from .views import _ensure_scene_art  # background generator trigger

# ── Branding ───────────────────────────────────────────────────────────────────
admin.site.site_header = "Bambicim Admin"
admin.site.site_title = "Bambicim Admin"
admin.site.index_title = "Welcome, sparkle guardian ✨"


# ── User + Inventory inline ────────────────────────────────────────────────────
class InventoryInline(admin.TabularInline):
    model = Inventory
    extra = 0
    autocomplete_fields = ("item",)
    fields = ("item", "qty")
    ordering = ("item__name",)


User = get_user_model()
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = [InventoryInline]
    search_fields = ("username", "email", "first_name", "last_name")
    list_display = ("username", "email", "inventory_total", "is_staff", "is_superuser", "last_login")
    list_filter = ("is_staff", "is_superuser", "is_active")

    @admin.display(description="Items")
    def inventory_total(self, obj):
        return obj.inventories.aggregate(s=Sum("qty"))["s"] or 0


# ── Items ──────────────────────────────────────────────────────────────────────
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("emoji", "name", "slug", "holders", "total_qty")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)

    @admin.display(description="Holders")
    def holders(self, obj):
        # number of distinct users who hold > 0 of this item
        return obj.inventory_set.filter(qty__gt=0).values("user").distinct().count()

    @admin.display(description="Total Qty")
    def total_qty(self, obj):
        return obj.inventory_set.aggregate(s=Sum("qty"))["s"] or 0


# ── Inventory ──────────────────────────────────────────────────────────────────
@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("user", "item", "qty")
    search_fields = ("user__username", "item__name", "item__slug")
    list_filter = ("item",)
    autocomplete_fields = ("user", "item")
    ordering = ("user__username", "item__name")
    actions = ["zero_out", "export_csv"]

    @admin.action(description="Set quantity to 0 for selected rows")
    def zero_out(self, request, queryset):
        updated = queryset.update(qty=0)
        self.message_user(request, f"Zeroed {updated} inventory rows.")

    @admin.action(description="Export selected to CSV")
    def export_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = "attachment; filename=inventory.csv"
        w = csv.writer(resp)
        w.writerow(["user", "item_slug", "item_name", "qty"])
        for r in queryset.select_related("user", "item"):
            w.writerow([r.user.username, r.item.slug, r.item.name, r.qty])
        return resp


# ── Sessions & logs ────────────────────────────────────────────────────────────
@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "started_at", "last_scene", "done")
    list_filter = ("done",)
    date_hierarchy = "started_at"
    search_fields = ("user__username", "last_scene")
    ordering = ("-started_at",)


@admin.register(ChoiceLog)
class ChoiceLogAdmin(admin.ModelAdmin):
    list_display = ("user", "scene", "choice", "made_at")
    search_fields = ("user__username", "scene", "choice")
    date_hierarchy = "made_at"
    list_filter = ("scene",)
    ordering = ("-made_at",)


# ── Narrative builder: Scenes → Choices → Gains ────────────────────────────────
class ChoiceGainInline(admin.TabularInline):
    model = ChoiceGain
    extra = 0
    autocomplete_fields = ("item",)
    fields = ("item", "qty")
    ordering = ("item__name",)


class ChoiceInline(admin.TabularInline):
    """Choices attached to a Scene (Choice.scene FK)."""
    model = Choice
    fk_name = "scene"
    extra = 1
    show_change_link = True
    autocomplete_fields = ("next_scene",)
    fields = ("code", "label", "order", "next_scene", "href", "action", "if_flags", "set_flags")
    ordering = ("order", "code")


@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "is_start", "art_status", "art_preview")
    list_filter = ("is_start",)
    search_fields = ("key", "title")
    inlines = [ChoiceInline]
    ordering = ("key",)
    actions = ["generate_art"]

    # helpers
    def _get_art(self, obj):
        from .models import SceneArt
        return SceneArt.objects.filter(key=obj.key).only("status", "image_webp").first()

    @admin.display(description="Art")
    def art_status(self, obj):
        a = self._get_art(obj)
        return getattr(a, "status", "—")

    @admin.display(description="Preview")
    def art_preview(self, obj):
        a = self._get_art(obj)
        if not a or not a.image_webp:
            return "—"
        b64 = base64.b64encode(a.image_webp).decode("ascii")
        return format_html('<img src="data:image/webp;base64,{}" style="height:48px;border-radius:6px" />', b64)

    @admin.action(description="(Re)generate pixel art for selected scenes")
    def generate_art(self, request, queryset):
        for s in queryset:
            _ensure_scene_art(s.key)
        self.message_user(request, f"Queued art for {queryset.count()} scene(s).")


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ("scene", "code", "label", "order", "next_scene", "href", "action")
    list_filter = ("scene",)
    search_fields = ("label", "scene__key", "code")
    autocomplete_fields = ("scene", "next_scene")
    inlines = [ChoiceGainInline]
    ordering = ("scene__key", "order", "code")


# ── Achievements ───────────────────────────────────────────────────────────────
@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "rule_type", "rule_param", "threshold", "is_active")
    list_filter = ("rule_type", "is_active")
    search_fields = ("slug", "name", "rule_param")


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ("user", "achievement", "achieved_at")
    list_filter = ("achievement",)
    search_fields = ("user__username", "achievement__slug")


# ── Scene pixel art cache ──────────────────────────────────────────────────────
@admin.register(SceneArt)
class SceneArtAdmin(admin.ModelAdmin):
    list_display = ("key", "status", "updated_at", "preview")
    search_fields = ("key",)
    actions = ["regenerate_selected"]
    readonly_fields = ("updated_at", "preview")

    @admin.display(description="Preview")
    def preview(self, obj):
        if not obj.image_webp:
            return "—"
        b64 = base64.b64encode(obj.image_webp).decode("ascii")
        return format_html('<img src="data:image/webp;base64,{}" style="height:120px;border-radius:8px" />', b64)

    @admin.action(description="Regenerate pixel art")
    def regenerate_selected(self, request, queryset):
        count = 0
        for row in queryset:
            row.status = "pending"
            row.save(update_fields=["status", "updated_at"])
            _ensure_scene_art(row.key)  # queue background regeneration
            count += 1
        self.message_user(request, f"Queued regeneration for {count} scene(s).")


# ── (optional) Analytics scaffolding — activates when model exists ─────────────
# Add this model later in core/models.py to start logging page/API traffic:
# class TrafficEvent(models.Model):
#     KIND_CHOICES = [("visit","Visit"),("api","API Call")]
#     kind = models.CharField(max_length=8, choices=KIND_CHOICES)
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
#     path = models.CharField(max_length=512, blank=True)
#     method = models.CharField(max_length=8, blank=True)
#     ip = models.GenericIPAddressField(null=True, blank=True)
#     user_agent = models.TextField(blank=True)
#     provider = models.CharField(max_length=64, blank=True)  # e.g., "openai"
#     model = models.CharField(max_length=64, blank=True)     # e.g., "gpt-4o"
#     tokens_in = models.IntegerField(default=0)
#     tokens_out = models.IntegerField(default=0)
#     success = models.BooleanField(default=True)
#     latency_ms = models.IntegerField(default=0)
#     created_at = models.DateTimeField(auto_now_add=True)

try:
    from .models import TrafficEvent  # if you add it later, admin auto-enables
except Exception:
    TrafficEvent = None

if TrafficEvent:
    @admin.register(TrafficEvent)
    class TrafficEventAdmin(admin.ModelAdmin):
        list_display = ("created_at", "kind", "user", "path", "provider", "model", "tokens_in", "tokens_out", "success")
        list_filter = ("kind", "provider", "model", "success")
        date_hierarchy = "created_at"
        search_fields = ("user__username", "path", "user_agent", "provider", "model")
        readonly_fields = ("created_at",)
