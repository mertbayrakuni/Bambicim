# Bambicim/asgi.py
import os

from channels.routing import ProtocolTypeRouter, URLRouter
from core.consumers import BambiConsumer  # birazdan oluşturacağız
from django.core.asgi import get_asgi_application
from django.urls import path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Bambicim.settings")

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter([
        path("ws", BambiConsumer.as_asgi()),
    ]),
})
