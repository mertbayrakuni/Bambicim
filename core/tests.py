import pytest

@pytest.fixture(autouse=True)
def disable_ssl_redirect(settings):
    settings.SECURE_SSL_REDIRECT = False
    # If you have HSTS or proxy SSL headers, also neutralize them for tests:
    settings.SECURE_HSTS_SECONDS = 0
    settings.SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    settings.SECURE_HSTS_PRELOAD = False
    settings.SECURE_PROXY_SSL_HEADER = None
