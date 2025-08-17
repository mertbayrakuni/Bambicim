from django.http import HttpResponsePermanentRedirect

CANONICAL_HOST = "bambicim.com"

class CanonicalHostRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0]
        if host != CANONICAL_HOST:
            url = f"https://{CANONICAL_HOST}{request.get_full_path()}"
            return HttpResponsePermanentRedirect(url)
        return self.get_response(request)
