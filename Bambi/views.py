from django.shortcuts import render
import logging
from utils.helpers import persona_from_color, utcnow_iso

log = logging.getLogger("app")


def index(request):
    persona = persona_from_color(request.GET.get("color", "white"))
    log.info("Page hit at %s persona=%s", utcnow_iso(), persona["name"])

from django.shortcuts import render

def home(request):
    return render(request, "index.html")
