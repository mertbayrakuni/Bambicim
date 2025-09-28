from __future__ import annotations

import requests
import uuid

from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from copilot.models import Doc


class Command(BaseCommand):
    help = "Fetch a few bambicim.com pages and index them into Doc."

    def add_arguments(self, parser):
        parser.add_argument("--base", default="https://bambicim.com")
        parser.add_argument("--paths", nargs="*", default=["/", "/#work", "/#game", "/#contact"])

    def handle(self, *a, **kw):
        base = kw["base"].rstrip("/")
        paths = kw["paths"]
        for p in paths:
            url = base + ("" if p.startswith("/") else "/") + p
            self.stdout.write(f"Fetch {url}")
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            # crude main content selection
            for s in soup(["script", "style", "nav", "footer"]): s.decompose()
            title = soup.title.get_text(strip=True) if soup.title else url
            text = soup.get_text("\n", strip=True)

            # upsert by url
            d = Doc.objects.filter(url=url).first()
            if not d:
                d = Doc(id=uuid.uuid4().hex[:24], url=url, kind="page")
            d.title, d.text = title, text
            d.save()
        self.stdout.write(self.style.SUCCESS("Indexed."))
