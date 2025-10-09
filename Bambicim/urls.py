# Bambicim/urls.py

from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include, reverse, re_path
from django.views.generic import TemplateView
from django.views.static import serve as media_serve

from accounts import views as accounts_views
from blog.feeds import LatestPostsFeed
from copilot import views as copilot  # ← SSE + uploads
from core import views as core  # ← single, unambiguous alias
from portfolio.sitemaps import ProjectSitemap


# ---- Sitemaps ---------------------------------------------------------------
class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        # Only real URL names (no #anchors)
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
    path("", core.home, name="home"),
    path("contact/", core.contact, name="contact"),
    path("healthz", core.healthz, name="healthz"),

    # auth & profile
    path("accounts/", include("django.contrib.auth.urls")),  # login/logout/password*
    path("accounts/signup/", accounts_views.signup, name="signup"),
    path("accounts/me/", accounts_views.profile_page, name="profile"),
    path("accounts/clear/", core.inventory_clear, name="inventory_clear"),

    # game
    path("game/choice", core.game_choice, name="game_choice"),
    path("game/inventory", core.game_inventory, name="game_inventory"),
    path("game/scenes", core.game_scenes_json, name="game_scenes_json"),
    path("game/achievements", core.game_achievements, name="game_achievements"),

    # pixel art
    path("art/scene/<str:scene_key>/ensure", core.scene_art_ensure, name="scene_art_ensure"),
    path("art/scene/<str:scene_key>.webp", core.scene_art_image, name="scene_art_image"),
    path("art/ensure-all", core.scene_art_ensure_all, name="scene_art_ensure_all"),

    # chatbot (HTTP) — used by initialText & fallback paths in chatbot.js
    path("api/chat", core.api_chat, name="api_chat"),

    # copilot (SSE) — used by chatbot.js streaming
    path("api/copilot/upload", copilot.upload, name="copilot_upload"),
    path("api/copilot/chat", copilot.chat, name="copilot_chat"),

    # static pages
    path("about/", TemplateView.as_view(template_name="static/about.html"), name="about"),
    path("privacy/", TemplateView.as_view(template_name="static/privacy.html"), name="privacy"),
    path("terms/", TemplateView.as_view(template_name="static/terms.html"), name="terms"),
    path("sitemap/", TemplateView.as_view(template_name="static/sitemap.html"), name="sitemap_html"),

    # robots + XML sitemap
    path("robots.txt",
         TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
         name="robots"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),

    # blog
    path("blog/", include("blog.urls", namespace="blog")),
    path("blog/rss/", LatestPostsFeed(), name="blog_rss"),

    # search
    path("", include("core.urls")),
]

urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", media_serve, {
        "document_root": settings.MEDIA_ROOT,
        "show_indexes": True,  # handy while debugging
    }),
]
