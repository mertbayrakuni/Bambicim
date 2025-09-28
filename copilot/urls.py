from django.urls import path

from . import views

urlpatterns = [
    path("chat", views.chat_sse, name="copilot_chat"),
    path("upload", views.upload_files, name="copilot_upload"),
    path("search", views.search_api, name="copilot_search"),
    path("threads/<str:cid>", views.thread_get, name="copilot_thread"),
]
