# Bambicim

Princess‑pink software, built fast & beautifully — notes, blog, and shiny experiments from **Bambi**.

**Live:** https://bambicim.com • **Stack:** Django, PostgreSQL, Whitenoise, Markdown, Requests, Render

---

## ✨ Features

- **Homepage** with hero, selected work, Bambi Game, and contact form.
- **Blog** (full system):
  - Models: `Category`, `Tag`, `Post`, `PostImage`.
  - States: **Draft**, **Scheduled**, **Published** (auto‑publish at `publish_at`).
  - Covers, excerpts, Markdown content (`blog/templatetags/blog_extras.py`).
  - Index `/blog/` and detail pages `/blog/YYYY/MM/slug/`.
  - RSS feed at **`/blog/rss/`** (`name="blog_rss"`).
  - SEO: slugs, canonical URLs (optional), sitemap.
- **Bambi Game** (front‑end mini narrative game) stored under `core/static/game/`.
- **Chatbot / Copilot** with file uploads and SSE streaming (site assistant).
- **Production‑ready Django**: env‑driven settings, security headers, Whitenoise, cached GitHub API, basic email config.
- **Sitemaps & robots**:
  - `sitemap.xml` with Projects + Blog Posts.
  - `robots.txt` and an HTML sitemap at `/sitemap/`.
- **Static & Media**:
  - `STATIC_URL=/static/` (collected by Whitenoise).
  - `MEDIA_URL=/media/` (user uploads like blog covers).

---

## 🗂 Project layout (important bits)

```
Bambicim/
├─ Bambicim/                   # Django project
│  ├─ settings.py             # env‑first config
│  └─ urls.py                 # routes, sitemaps, blog include
├─ accounts/                  # auth views (login/signup/profile)
├─ blog/                      # blog app
│  ├─ admin.py
│  ├─ feeds.py                # /blog/rss/
│  ├─ models.py               # Category, Tag, Post, PostImage
│  ├─ sitemaps.py             # BlogPostSitemap
│  ├─ templatetags/blog_extras.py  # markdown, helpers
│  ├─ urls.py                 # /blog/ index & details
│  └─ templates/blog/         # index.html, detail.html
├─ core/                      # site + game + contact form
├─ portfolio/                 # portfolio projects + sitemap
├─ utils/github.py            # Selected work — GitHub API client
├─ pytest.ini                 # pytest config
└─ .github/workflows/ci.yml   # CI: ruff + pytest + collectstatic
```

---

## 🔧 Local development

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# DB
python manage.py migrate
python manage.py createsuperuser  # optional (admin access)

# Run
python manage.py runserver
```

Create a `.env` in the repo root (values shown are safe defaults for local):

```env
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=change-me
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

# Database (prefer your local Postgres)
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DB
DJANGO_DB_SSL=0

# Canonical host redirector (optional in dev)
# CANONICAL_HOST=bambicim.com

# GitHub (for Selected Work; token optional)
GITHUB_USERNAME=mertbayrakuni
# GITHUB_TOKEN=ghp_xxx
```

### Media & static in dev

- Static files are served by Django + Whitenoise.
- Media (uploads) are served by Django when `DJANGO_SERVE_MEDIA=1` (dev only).

```env
DJANGO_SERVE_MEDIA=1
MEDIA_URL=/media/
MEDIA_ROOT=./media
```

---

## ☁️ Deploying on Render

1) **Add a Disk** to the **web service**  
   - *Mount path:* `/opt/render/project/src/media`  
   - *Size:* start with 1–10 GB (can grow later).

2) **Env vars** on the service
```
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=***
DJANGO_ALLOWED_HOSTS=bambicim.com,www.bambicim.com
DATABASE_URL=postgres://... (internal URL)
DJANGO_DB_SSL=0                # Render internal Postgres doesn’t need SSL
MEDIA_ROOT=/opt/render/project/src/media
MEDIA_URL=/media/
DJANGO_SERVE_MEDIA=1           # keep until you move media to S3/Cloudinary
GITHUB_USERNAME=mertbayrakuni
# GITHUB_TOKEN=ghp_xxx         # optional (higher API rate limits)
```

3) **Build & Start** (Render settings)
```
Build command:  pip install -r requirements.txt && python manage.py collectstatic --noinput
Start command:  gunicorn Bambicim.wsgi:application --preload
Post-deploy:    python manage.py migrate
```

> When you later move uploads to S3/Cloudinary: remove `DJANGO_SERVE_MEDIA`, set `DEFAULT_FILE_STORAGE`, and unset the Disk.

---

## 📰 Blog authoring

- Add posts in **Admin → Blog → Posts**.
- Fill: Title, Slug (auto), Excerpt, Content (Markdown supported), Category, Tags, Cover image.
- Choose **Draft / Scheduled / Published** and (optionally) **Publish at** future date.
- Use the **“featured”** toggle to pin a post on the index.
- RSS feed: `/blog/rss/` (add `<link rel="alternate" type="application/rss+xml" title="Bambicim Blog RSS" href="{% url 'blog_rss' %}">` inside `base.html` `<head>`).

---

## 🔍 Sitemaps & robots

- `sitemap.xml` includes Portfolio and Blog posts.
- `robots.txt` and an HTML site map at `/sitemap/` are routed in `Bambicim/urls.py`.

---

## 🤖 CI (GitHub Actions)

`ci.yml` runs:
- **Ruff** for linting (line‑length 100).
- **pytest** (fast, minimal smoke tests).
- Django system checks + `collectstatic` sanity.

> If CI fails on style only, run locally:
```bash
ruff check . --fix
```

To relax line‑length to 120, set it in `ruff.toml`:
```toml
line-length = 120
```

---

## ✅ Tests

- `pytest.ini` is included; run `pytest -q` locally.
- Minimal smoke tests live under `core/tests/`.
- Add tests per app (e.g., `blog/tests/`) as your content grows.

---

## 🧠 “Selected work” (GitHub)

`utils/github.py` fetches the latest 3 public repos for the configured `GITHUB_USERNAME` and caches for 10 minutes. If a repo becomes private, it simply disappears from the list.

---

## 🗺️ Useful management commands

```bash
# Rebuild the Copilot index from the live site (with optional fallbacks)
python manage.py copilot_index --sleep 0.1 --ignore_errors

# Regenerate pixel art for scenes (game)
python manage.py regen_scene_art --all
```

---

## 🛡️ Notes on security & email

- Emails use `EMAIL_BACKEND` env override; in local dev it prints to console.
- Canonical host redirects enforce a single public hostname when `CANONICAL_HOST` is set and `DEBUG=False`.

---

## 👩🏻‍💻 Conventions

- Python ≥ 3.11
- Format/organize imports with Ruff. Prefer small functions; avoid one‑line `if`/`for` style (keeps CI happy).
- Templates follow the `.b-container` layout grid and “princess‑pink” theme tokens.

---

## 📜 License

MIT © 2025 Bambi
