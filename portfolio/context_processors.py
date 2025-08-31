from .models import Project


def featured_projects(request):
    return {"featured_projects": Project.objects.filter(featured=True)[:8]}
