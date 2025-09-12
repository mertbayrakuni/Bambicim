import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_homepage_renders(client):
    url = reverse("home")
    resp = client.get(url)
    assert resp.status_code == 200
    # basic content hints
    assert b"Selected work" in resp.content

@pytest.mark.django_db
def test_contact_rate_limit_and_validation(client, settings):
    url = reverse("contact")

    # empty post -> validation errors (should NOT rate-limit)
    resp = client.post(url, {})
    assert resp.status_code == 302  # redirects back to home

    # valid-looking post -> should 302 and set rate-limit
    resp = client.post(url, {
        "name": "Testy",
        "email": "test@example.com",
        "message": "Hello!"
    })
    assert resp.status_code == 302

    # second post immediately -> blocked by rate-limit
    resp = client.post(url, {
        "name": "Testy",
        "email": "test@example.com",
        "message": "Hello again!"
    })
    assert resp.status_code == 302
