from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView

from .models import Post, Category, Tag


class BasePostList(ListView):
    model = Post
    paginate_by = 10
    context_object_name = "posts"
    template_name = "blog/index.html"

    def get_queryset(self):
        qs = Post.objects.published().select_related("author", "category").prefetch_related("tags")
        return qs


class BlogIndexView(BasePostList):
    pass


class CategoryView(BasePostList):
    def get_queryset(self):
        cat = get_object_or_404(Category, slug=self.kwargs["slug"])
        return super().get_queryset().filter(category=cat)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["category"] = get_object_or_404(Category, slug=self.kwargs["slug"])
        return ctx


class TagView(BasePostList):
    def get_queryset(self):
        tag = get_object_or_404(Tag, slug=self.kwargs["slug"])
        return super().get_queryset().filter(tags=tag)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tag"] = get_object_or_404(Tag, slug=self.kwargs["slug"])
        return ctx


class PostDetailView(DetailView):
    model = Post
    context_object_name = "post"
    template_name = "blog/detail.html"

    def get_object(self, queryset=None):
        year = self.kwargs["year"]
        month = f"{int(self.kwargs['month']):02d}"
        slug = self.kwargs["slug"]
        obj = get_object_or_404(Post.objects.published(), slug=slug)
        # soft check on date, but do not 404 if month mismatch; SEO friendly
        if obj.publish_at.strftime("%Y") != str(year):
            pass
        if obj.publish_at.strftime("%m") != str(month):
            pass
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        post = ctx["post"]
        # related posts by tag (simple)
        related = (
            Post.objects.published()
            .filter(tags__in=post.tags.all())
            .exclude(pk=post.pk)
            .distinct()[:4]
        )
        ctx["related_posts"] = related
        return ctx
