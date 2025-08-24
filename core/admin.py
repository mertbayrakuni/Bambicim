# core/admin.py
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Sum

from .models import Item, Inventory, GameSession, ChoiceLog

# --- Branding (nice touch) ---
admin.site.site_header = "Bambicim Admin"
admin.site.site_title = "Bambicim Admin"
admin.site.index_title = "Welcome, sparkle guardian ✨"


# --- Inline: show a user's inventory on their user page ---
class InventoryInline(admin.TabularInline):
    model = Inventory
    extra = 0
    autocomplete_fields = ("item",)
    fields = ("item", "qty")
    readonly_fields = ()
    ordering = ("item__name",)


# --- Extend the default User admin to include inventory inline ---
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


# --- Items ---
@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("emoji", "name", "slug", "holders", "total_qty")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # annotate how many users have this item, and total qty
        return qs.annotate(
            _holders=Sum("inventory__qty__gt"),  # Django won't aggregate booleans, we compute below
            _total=Sum("inventory__qty"),
        )

    def holders(self, obj):
        # fallback if DB can’t aggregate boolean; count non-zero rows
        return obj.inventory_set.exclude(qty=0).count()

    holders.short_description = "Holders"

    def total_qty(self, obj):
        return obj.inventory_set.aggregate(s=Sum("qty"))["s"] or 0

    total_qty.short_description = "Total Qty"


# --- Inventory ---
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


# --- Sessions ---
@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "started_at", "last_scene", "done")
    list_filter = ("done",)
    date_hierarchy = "started_at"
    search_fields = ("user__username", "last_scene")
    ordering = ("-started_at",)


# --- Choice logs ---
@admin.register(ChoiceLog)
class ChoiceLogAdmin(admin.ModelAdmin):
    list_display = ("user", "scene", "choice", "made_at")
    search_fields = ("user__username", "scene", "choice")
    date_hierarchy = "made_at"
    list_filter = ("scene",)
    ordering = ("-made_at",)
