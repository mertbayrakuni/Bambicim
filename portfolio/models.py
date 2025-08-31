from django.db import models


class Project(models.Model):
    title = models.CharField(max_length=120)
    short_desc = models.TextField(blank=True)
    url = models.URLField(blank=True)
    cover_image = models.ImageField(upload_to="projects/", blank=True, null=True)  # see media note below
    tech_tags = models.CharField(max_length=200, blank=True, help_text="Comma-separated tags")
    featured = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def tags_list(self):
        return [t.strip() for t in (self.tech_tags or "").split(",") if t.strip()]
