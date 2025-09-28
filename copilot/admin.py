from django.contrib import admin
from .models import Conversation, Message, Attachment, Doc

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id","title","user","created_at","updated_at")
    search_fields = ("id","title","user__username")

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id","conversation","role","created_at")
    search_fields = ("id","content_md","conversation__id")

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("id","conversation","mime","size","created_at")
    search_fields = ("id","file","conversation__id","sha256")

@admin.register(Doc)
class DocAdmin(admin.ModelAdmin):
    list_display = ("id","kind","title","slug","url","updated_at")
    search_fields = ("title","slug","url","text")
