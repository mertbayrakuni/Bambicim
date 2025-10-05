# conftest.py (repo root)
import pytest

@pytest.fixture(autouse=True)
def _test_sane_http(settings):
    # Kill HTTPS + HSTS so test client doesn't get 301 to https://
    settings.SECURE_SSL_REDIRECT = False
    settings.SECURE_HSTS_SECONDS = 0
    settings.SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    settings.SECURE_HSTS_PRELOAD = False
    settings.SECURE_PROXY_SSL_HEADER = None

    # Kill trailing-slash auto-redirects (e.g. /contact -> /contact/)
    # so posts/gets hit the view directly in tests.
    settings.APPEND_SLASH = False
