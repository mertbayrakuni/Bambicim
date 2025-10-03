from django.contrib.syndication.views import Feed

from .models import Post


class LatestPostsFeed(Feed):
    title = "Bambicim Blog"
    link = "/blog/"
    description = "Latest posts from Bambicim blog"

    def items(self):
        return Post.objects.published()[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.excerpt or item.seo_description or item.title

    def item_link(self, item):
        return item.get_absolute_url()
