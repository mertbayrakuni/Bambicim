# core/admin.py
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Sum

from .models import Achievement, UserAchievement
from .models import (
    Item, Inventory, GameSession, ChoiceLog,
    Scene, Choice, ChoiceGain,
)

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
    list_display = ("username", "email", "is_staff", "is_superuser", "last_login")
    list_filter = ("is_staff", "is_superuser", "is_active")


# ── Items ──────────────────────────────────────────────────────────────────────
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("emoji", "name", "slug", "holders", "total_qty")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)

    # Robust counts (avoids DB-specific 500s)
    def holders(self, obj):
        # number of distinct users who hold > 0 of this item
        return obj.inventory_set.filter(qty__gt=0).values("user").distinct().count()

    holders.short_description = "Holders"

    def total_qty(self, obj):
        return obj.inventory_set.aggregate(s=Sum("qty"))["s"] or 0

    total_qty.short_description = "Total Qty"


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
    """
    Choices attached to a Scene. NB: the model also has `next_scene` FK to Scene,
    so we must tell Django which FK links this inline to the parent.
    """
    model = Choice
    fk_name = "scene"  # ← fixes “more than one ForeignKey to Scene” error
    extra = 1
    show_change_link = True
    autocomplete_fields = ("next_scene",)
    fields = ("code", "label", "order", "next_scene", "href", "action", "if_flags", "set_flags")
    ordering = ("order", "code")


@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "is_start")
    list_filter = ("is_start",)
    search_fields = ("key", "title")
    inlines = [ChoiceInline]
    ordering = ("key",)


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ("scene", "code", "label", "order", "next_scene", "href", "action")
    list_filter = ("scene",)
    search_fields = ("label", "scene__key", "code")
    autocomplete_fields = ("scene", "next_scene")
    inlines = [ChoiceGainInline]
    ordering = ("scene__key", "order", "code")


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
