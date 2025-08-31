from django.contrib.sitemaps import Sitemap
from .models import Project


class ProjectSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Project.objects.filter(featured=True)

    def lastmod(self, obj):
        return obj.created_at
