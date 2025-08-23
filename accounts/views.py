from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from core.models import Inventory


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # auto-login after signup
            return redirect("/")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def profile_page(request):
    rows = (
        Inventory.objects.filter(user=request.user)
        .select_related("item")
        .order_by("item__name")
    )
    return render(request, "profile.html", {"rows": rows})
