import logging
from django.contrib import messages
from django.core.mail import send_mail, BadHeaderError
from django.shortcuts import render, redirect
from django.conf import settings
import os
from utils.github import get_recent_public_repos_cached

log = logging.getLogger("app")


def home(request):
    user = os.environ.get("GITHUB_USERNAME", "mertbayrakuni")
    token = os.environ.get("GITHUB_TOKEN")  # optional
    repos = []
    try:
        repos = get_recent_public_repos_cached(user, token)
    except Exception:
        repos = []  # fail silently; page still loads
    return render(request, "home.html", {"repos": repos})


def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        msg = request.POST.get("message", "").strip()
        if not (name and email and msg):
            messages.error(request, "Please fill in all fields.")
            return redirect("home")
        subject = f"New lead — Bambicim: {name}"
        body = f"From: {name} <{email}>\n\n{msg}"
        try:
            send_mail(subject, body,
                      settings.DEFAULT_FROM_EMAIL,
                      ["mert@bambicim.com", "ipek@bambicim.com"],
                      fail_silently=False)
            messages.success(request, "Thanks! We’ll get back to you shortly.")
        except BadHeaderError:
            messages.error(request, "Invalid header found.")
        return redirect("home")
    return redirect("home")
