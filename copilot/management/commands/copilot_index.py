# copilot/management/commands/copilot_index.py
from __future__ import annotations

import time
import uuid
from urllib.parse import urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from copilot.models import Doc


def _make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    })
    retry = Retry(
        total=4,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s


class Command(BaseCommand):
    help = "Fetch a few bambicim.com pages and index them into Doc."

    def add_arguments(self, parser):
        parser.add_argument("--base", default="https://bambicim.com")
        parser.add_argument("--paths", nargs="*", default=["/", "/#work", "/#game", "/#contact"])
        parser.add_argument("--alt_base", default=None, help="Fallback base (e.g., http://127.0.0.1:8000)")
        parser.add_argument("--ignore_errors", action="store_true")
        parser.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between requests")

    def handle(self, *a, **kw):
        base = kw["base"].rstrip("/")
        alt_base = (kw.get("alt_base") or "").rstrip("/") or None
        paths = kw["paths"]
        sess = _make_session()

        for p in paths:
            url = base + ("" if p.startswith("/") else "/") + p
            sp = urlsplit(url)
            fetch_url = urlunsplit((sp.scheme, sp.netloc, sp.path or "/", sp.query, ""))

            self.stdout.write(f"Fetch {fetch_url}  (store as {url})")
            html = None
            for attempt in (1, 2):
                try:
                    r = sess.get(fetch_url, timeout=15)
                    if r.status_code >= 400:
                        r.raise_for_status()
                    html = r.text
                    break
                except Exception as e:
                    if attempt == 1 and alt_base:
                        # try fallback base once
                        alt_url = alt_base + ("" if p.startswith("/") else "/") + p
                        sp2 = urlsplit(alt_url)
                        fetch_url = urlunsplit((sp2.scheme, sp2.netloc, sp2.path or "/", sp2.query, ""))
                        self.stdout.write(self.style.WARNING(f"{e} → retry via alt_base: {fetch_url}"))
                        continue
                    if kw.get("ignore_errors"):
                        self.stderr.write(self.style.WARNING(f"Skip {url}: {e}"))
                        html = None
                        break
                    raise

            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            text = None
            if sp.fragment:
                target = soup.find(id=sp.fragment)
                if target:
                    container = target.find_parent(["section", "div", "main"]) or target
                    text = container.get_text("\n", strip=True)

            if not text:
                main = soup.find("main") or soup.body or soup
                text = main.get_text("\n", strip=True)

            title = soup.title.get_text(strip=True) if soup.title else fetch_url

            d = Doc.objects.filter(url=url).first()
            if not d:
                d = Doc(id=uuid.uuid4().hex[:24], url=url, kind="page")
            d.title, d.text = title, text
            d.save()

            if kw["sleep"]:
                time.sleep(kw["sleep"])

        self.stdout.write(self.style.SUCCESS("Indexed."))
