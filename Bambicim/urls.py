from django.contrib import admin
from django.urls import path, include
from core.views import home, contact
from core import views as core_views
from accounts import views as accounts_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("contact/", contact, name="contact"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/signup/", accounts_views.signup, name="signup"),
    path("game/choice", core_views.game_choice, name="game_choice"),
    path("game/inventory", core_views.game_inventory, name="game_inventory"),
    path("accounts/me/", accounts_views.profile_page, name="profile"),
    path("", include("django.contrib.auth.urls")),
]
