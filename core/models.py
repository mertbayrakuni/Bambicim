from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class Item(models.Model):
    slug = models.SlugField(primary_key=True)
    name = models.CharField(max_length=100)
    emoji = models.CharField(max_length=8, default="🦋")

    def __str__(self):
        return f"{self.emoji} {self.name}"


class Inventory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="inventories")
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    qty = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "item"], name="unique_user_item")
        ]

    def __str__(self):
        return f"{self.user} • {self.item} × {self.qty}"


class GameSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    last_scene = models.CharField(max_length=100, blank=True, default="")
    done = models.BooleanField(default=False)


class ChoiceLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="choice_logs"
    )
    scene = models.CharField(max_length=64)
    choice = models.CharField(max_length=64, blank=True, null=True)
    made_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} @ {self.scene} → {self.choice}"
