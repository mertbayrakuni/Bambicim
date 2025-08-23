# Bambicim

Princess‑pink software, built fast & beautifully — notes, builds, and shiny experiments from **Bambi**.

Live: **bambicim.com** · Stack: Django, Postgres, Whitenoise, Requests, Render

---

## ✨ What’s inside

- **Homepage** with an elegant hero and contact section.
- **Selected work** — shows the **latest 3 public GitHub repos** for `mertbayrakuni` dynamically (GitHub API + caching).
- **Bambi Game** — a gentle, narrative mini‑game embedded on the homepage.
  - Content JSON: `core/static/game/scenes.json`
  - Engine: `core/static/game/engine.js` (flags, autosave, back, reset)
- **Production‑ready Django** (db URL parsing, static, env, security).

---

## 🗂️ Project structure

```
Bambicim/
├─ Bambicim/                 # Django project (settings/urls/wsgi)
├─ core/
│  ├─ static/
│  │  ├─ css/style.css
│  │  ├─ js/script.js
│  │  └─ game/
│  │     ├─ engine.js
│  │     └─ scenes.json
│  └─ templates/
│     ├─ base.html
│     └─ home.html
├─ utils/
│  └─ github.py              # GitHub API client for "Selected work"
├─ requirements.txt
└─ manage.py
```

---

## 🚀 Local dev

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Create `.env` for local:

```env
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=change-me
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

# Use External URL for Render Postgres locally (append ?sslmode=require)
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DB?sslmode=require
DJANGO_DB_SSL=1

# GitHub (optional token)
GITHUB_USERNAME=mertbayrakuni
# GITHUB_TOKEN=ghp_xxx
```

---

## ☁️ Deploy (Render)

Set env vars on your web service: `DATABASE_URL` (Internal URL), `DJANGO_DB_SSL=0`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`, email vars, and `GITHUB_USERNAME` (+ optional `GITHUB_TOKEN`).

Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`  
Start: `gunicorn Bambicim.wsgi:application --preload`  
Post‑deploy: `python manage.py migrate`

---

## 🧠 Selected work (how it works)

`utils/github.py` fetches the 3 most recently updated public repos and caches the result for 10 minutes. If you make a repo private, it simply won’t show—no breakage.

---

## 🎮 Extending the Bambi Game

Add scenes in `core/static/game/scenes.json` (branch with `"choices"`, set flags with `"set"`, gate with `"if"`). Target: ~1 hour playtime with 5–6 chapters.

---

## 📜 License

MIT © 2025 Bambi
