from django.contrib import admin
from django.urls import path, include
from core.views import home, contact

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("contact/", contact, name="contact"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/signup/", accounts_views.signup, name="signup"),
]
