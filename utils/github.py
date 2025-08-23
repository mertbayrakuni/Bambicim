# utils/github.py
import os, requests, time
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

GITHUB_API = "https://api.github.com"

def _normalize(repo):
    pushed = parse_datetime(repo.get("pushed_at"))
    if pushed and timezone.is_naive(pushed):
        pushed = pushed.replace(tzinfo=timezone.utc)
        cache_bust = int(time.time() // 3600)
    return {
        "name": repo["name"],
        "full_name": repo["full_name"],
        "html_url": repo["html_url"],
        "description": repo.get("description"),
        "language": repo.get("language"),
        "stars": repo.get("stargazers_count", 0),
        "pushed_dt": pushed,
        "og_image": f"https://opengraph.githubassets.com/{cache_bust}/{repo['full_name']}",
    }

def fetch_recent_public_repos(user: str, token: str | None, per_page: int = 3):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "bambicim-site",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {"sort": "pushed", "direction": "desc", "per_page": per_page, "type": "public"}
    r = requests.get(f"{GITHUB_API}/users/{user}/repos", headers=headers, params=params, timeout=6)
    r.raise_for_status()
    data = r.json()
    # If GitHub returns something unexpected, fall back gracefully
    if not isinstance(data, list):
        return []
    return [_normalize(repo) for repo in data[:per_page]]

def get_recent_public_repos_cached(user: str, token: str | None):
    key = f"gh:recent:{user}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        repos = fetch_recent_public_repos(user, token)
    except Exception:
        # keep the page alive; return last cached if present
        repos = cached or []
    cache.set(key, repos, 600)  # 10 minutes
    return repos

