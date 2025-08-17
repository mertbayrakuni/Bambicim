# Bambicim/middleware.py
from django.http import HttpResponsePermanentRedirect


class CanonicalHostRedirectMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response
        self.canonical_host = "bambicim.com"

    def __call__(self, request):
        host = request.get_host().split(":")[0]
        if host != self.canonical_host:
            return HttpResponsePermanentRedirect(
                f"https://{self.canonical_host}{request.get_full_path()}"
            )
        return self.get_response(request)
