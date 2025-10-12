# core/middleware.py
from django.http import HttpResponseNotFound

from .models import TrafficEvent

SKIP_PREFIXES = ("/admin/", "/static/", "/media/", "/healthz", "/favicon.ico")


class TrafficMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(SKIP_PREFIXES):
            try:
                TrafficEvent.objects.create(
                    kind="visit",
                    user=(request.user if getattr(request, "user", None) and request.user.is_authenticated else None),
                    path=request.path[:512],
                    method=request.method[:8],
                    ip=(request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                        or request.META.get("REMOTE_ADDR")),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:4000],
                )
            except Exception:
                # never break the request pipeline
                pass
        return self.get_response(request)


def block_wp_probe(get_response):
    def middleware(request):
        p = request.path.lower()
        if "/wp-" in p or p.endswith("/wlwmanifest.xml"):
            return HttpResponseNotFound()
        return get_response(request)

    return middleware
