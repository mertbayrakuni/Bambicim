# Bambicim/middleware.py
import os

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalHostRedirectMiddleware:
    """
    In PROD (DEBUG=False), permanently redirect every request to CANONICAL_HOST.
    Skip redirect for health/robots/sitemap. No redirects in local/dev.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Prefer settings, fall back to env. Default is set in settings.py
        self.canonical_host = getattr(settings, "CANONICAL_HOST", None) or os.getenv("CANONICAL_HOST")
        self.enabled = bool(self.canonical_host) and (not settings.DEBUG)

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        # Allow internal endpoints without redirect
        if request.path in ("/healthz", "/robots.txt", "/sitemap.xml"):
            return self.get_response(request)

        host = request.get_host().split(":")[0]
        if host != self.canonical_host:
            return HttpResponsePermanentRedirect(
                f"https://{self.canonical_host}{request.get_full_path()}"
            )
        return self.get_response(request)
