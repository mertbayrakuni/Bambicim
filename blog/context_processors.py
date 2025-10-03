from .models import Post


def latest_posts(request):
    return {"latest_posts": Post.objects.published()[:5]}
