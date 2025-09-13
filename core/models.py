# core/models.py
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Item(models.Model):
    slug = models.SlugField(primary_key=True)
    name = models.CharField(max_length=100)
    emoji = models.CharField(max_length=8, default="✨")

    def __str__(self): return f"{self.emoji} {self.name}"


class Inventory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="inventories")
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    qty = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "item"], name="unique_user_item")]

    def __str__(self): return f"{self.user} · {self.item} × {self.qty}"


class GameSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    last_scene = models.CharField(max_length=100, blank=True, default="")
    done = models.BooleanField(default=False)


class ChoiceLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="choice_logs")
    scene = models.CharField(max_length=64)
    choice = models.CharField(max_length=64, blank=True, null=True)
    made_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"{self.user} @ {self.scene} → {self.choice}"


class Scene(models.Model):
    key = models.SlugField(primary_key=True)  # e.g. "intro", "boutique"
    title = models.CharField(max_length=100)
    text = models.TextField(blank=True)
    is_start = models.BooleanField(default=False)  # the starting scene

    class Meta:
        ordering = ("key",)

    def __str__(self): return self.key


class Choice(models.Model):
    scene = models.ForeignKey(Scene, on_delete=models.CASCADE, related_name="choices")

    code = models.SlugField(max_length=64)
    label = models.CharField(max_length=100)

    next_scene = models.ForeignKey(
        Scene, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    href = models.CharField(max_length=255, blank=True)  # external link
    action = models.CharField(max_length=32, blank=True)  # special (e.g. "profile")

    # flags
    if_flags = models.JSONField(default=dict, blank=True)  # {"flag": true}
    set_flags = models.JSONField(default=dict, blank=True)  # {"flag": true}

    # display
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "code")
        unique_together = [("scene", "code")]

    def __str__(self):
        return f"{self.scene.key} · {self.label}"


class ChoiceGain(models.Model):
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE, related_name="gains")
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    qty = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [("choice", "item")]

    def __str__(self):
        return f"{self.choice} +{self.qty} {self.item.slug}"


class Achievement(models.Model):
    RULE_COLLECT_ITEM = "collect_item"  # rule_param = item slug
    RULE_COLLECT_COUNT = "collect_count"  # threshold = total qty
    RULE_REACH_SCENE = "reach_scene"  # rule_param = scene key

    RULES = [
        (RULE_COLLECT_ITEM, "Collect specific item"),
        (RULE_COLLECT_COUNT, "Collect total items (qty)"),
        (RULE_REACH_SCENE, "Reach scene"),
    ]

    slug = models.SlugField(primary_key=True, max_length=64)
    name = models.CharField(max_length=100)
    emoji = models.CharField(max_length=8, default="✨")
    description = models.TextField(blank=True)
    rule_type = models.CharField(max_length=32, choices=RULES)
    rule_param = models.CharField(max_length=128, blank=True, default="")
    threshold = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.emoji} {self.name}"


class UserAchievement(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    achieved_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("user", "achievement")]


class SceneArt(models.Model):
    key = models.CharField(max_length=64, unique=True, db_index=True)
    prompt = models.TextField()
    status = models.CharField(max_length=16, default="pending")  # pending|ready|failed
    image_webp = models.BinaryField(null=True, blank=True)  # raw webp bytes
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key} ({self.status})"
