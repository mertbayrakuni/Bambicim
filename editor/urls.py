from django.urls import path

from . import views

urlpatterns = [
    path("editor/", views.editor, name="editor"),
    path("api/presets", views.presets_json, name="editor_presets"),
    path("api/upload", views.upload_asset, name="editor_upload"),
    path("api/save", views.save_edit, name="editor_save"),
    path("api/list", views.list_edits, name="editor_list"),
    path("api/render", views.upload_render, name="editor_render"),
]
