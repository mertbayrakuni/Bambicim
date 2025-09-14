# Bambicim/asgi.py — HTTP only
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Bambicim.settings")
application = get_asgi_application()
