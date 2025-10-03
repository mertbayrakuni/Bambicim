from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.BlogIndexView.as_view(), name="index"),
    path("category/<slug:slug>/", views.CategoryView.as_view(), name="category"),
    path("tag/<slug:slug>/", views.TagView.as_view(), name="tag"),
    path("<int:year>/<int:month>/<slug:slug>/", views.PostDetailView.as_view(), name="detail"),
]
