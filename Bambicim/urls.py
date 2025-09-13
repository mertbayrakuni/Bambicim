from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.views.generic import TemplateView

from accounts import views as accounts_views
from core import views as core_views, views
from core.views import home, contact, healthz, inventory_clear
from portfolio.sitemaps import ProjectSitemap

sitemaps = {"projects": ProjectSitemap}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("contact/", contact, name="contact"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/signup/", accounts_views.signup, name="signup"),
    path("healthz", healthz),  # NEW

    # game
    path("game/choice", core_views.game_choice, name="game_choice"),
    path("game/inventory", core_views.game_inventory, name="game_inventory"),
    path("game/scenes", views.game_scenes_json, name="game_scenes_json"),
    path("game/achievements", core_views.game_achievements, name="game_achievements"),

    # profile
    path("accounts/me/", accounts_views.profile_page, name="profile"),
    path("accounts/clear/", inventory_clear, name="inventory_clear"),

    # robots + sitemap
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),

    # art
    path("art/scene/<str:scene_key>/ensure", core_views.scene_art_ensure, name="scene_art_ensure"),
    path("art/scene/<str:scene_key>.webp", core_views.scene_art_image, name="scene_art_image"),
    path("art/ensure-all", core_views.scene_art_ensure_all, name="scene_art_ensure_all"),
]
