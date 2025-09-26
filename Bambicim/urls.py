from django.contrib import admin
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include, reverse
from django.views.generic import TemplateView

from accounts import views as accounts_views
from core import views as core_views, views
from core.views import home, contact, healthz, inventory_clear
from portfolio.sitemaps import ProjectSitemap


# ---- Sitemaps (combine static + projects) -----------------------------------
class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        # only real URL names (no #anchors)
        return ["home", "about", "privacy", "terms", "login", "signup"]

    def location(self, item):
        return reverse(item)


sitemaps = {
    "static": StaticViewSitemap,
    "projects": ProjectSitemap,
}

# ---- URL patterns -----------------------------------------------------------
urlpatterns = [
    path("admin/", admin.site.urls),

    # core pages
    path("", home, name="home"),
    path("contact/", contact, name="contact"),
    path("healthz", healthz),  # keep as-is if your monitor pings /healthz

    # auth & profile
    path("accounts/", include("django.contrib.auth.urls")),  # login/logout/password*
    path("accounts/signup/", accounts_views.signup, name="signup"),
    path("accounts/me/", accounts_views.profile_page, name="profile"),
    path("accounts/clear/", inventory_clear, name="inventory_clear"),

    # game
    path("game/choice", core_views.game_choice, name="game_choice"),
    path("game/inventory", core_views.game_inventory, name="game_inventory"),
    path("game/scenes", views.game_scenes_json, name="game_scenes_json"),
    path("game/achievements", core_views.game_achievements, name="game_achievements"),

    # art
    path("art/scene/<str:scene_key>/ensure", core_views.scene_art_ensure, name="scene_art_ensure"),
    path("art/scene/<str:scene_key>.webp", core_views.scene_art_image, name="scene_art_image"),
    path("art/ensure-all", core_views.scene_art_ensure_all, name="scene_art_ensure_all"),

    # chatbot api
    path("api/chat", views.api_chat, name="api_chat"),

    # static pages (HTML)
    path("about/", TemplateView.as_view(template_name="static/about.html"), name="about"),
    path("privacy/", TemplateView.as_view(template_name="static/privacy.html"), name="privacy"),
    path("terms/", TemplateView.as_view(template_name="static/terms.html"), name="terms"),
    path("sitemap/", TemplateView.as_view(template_name="static/sitemap.html"), name="sitemap_html"),

    # robots + XML sitemap (single, final definitions)
    path("robots.txt",
         TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
         name="robots"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
]
