from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:100]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=40, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:60]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class PostQuerySet(models.QuerySet):
    def published(self):
        now = timezone.now()
        return self.filter(status="published", publish_at__lte=now)


class Post(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("published", "Published"),
    ]

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")

    excerpt = models.TextField(blank=True)
    content = models.TextField()
    cover_image = models.ImageField(upload_to="blog/covers/", blank=True, null=True)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft", db_index=True)
    publish_at = models.DateTimeField(default=timezone.now, db_index=True)
    featured = models.BooleanField(default=False, db_index=True)
    reading_time = models.PositiveIntegerField(default=0, help_text="Estimated minutes to read")

    seo_title = models.CharField(max_length=180, blank=True)
    seo_description = models.CharField(max_length=300, blank=True)
    canonical_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-publish_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "publish_at"]),
            models.Index(fields=["featured"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        return self.status == "published" and self.publish_at <= timezone.now()

    def get_absolute_url(self):
        return reverse(
            "blog:detail",
            kwargs={
                "year": self.publish_at.strftime("%Y"),
                "month": self.publish_at.strftime("%m"),
                "slug": self.slug,
            },
        )

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:170] or "post"
            # ensure uniqueness by adding id later if needed
            self.slug = base
        # compute reading time (simple words/220)
        words = len((self.content or "").split())
        self.reading_time = max(1, round(words / 220))
        super().save(*args, **kwargs)
        # after we have an id, ensure unique slug if clashes exist
        if Post.objects.exclude(pk=self.pk).filter(slug=self.slug).exists():
            self.slug = f"{self.slug}-{self.pk}"
            super().save(update_fields=["slug"])


class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="blog/gallery/")
    caption = models.CharField(max_length=140, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Image {self.id} for {self.post.title}"
