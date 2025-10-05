# blog/templatetags/blog_extras.py
from django import template
from django.conf import settings

register = template.Library()

try:
    import markdown as _md
except Exception:  # pragma: no cover
    _md = None


@register.filter
def markdownify(text):
    if not text:
        return ""
    if _md:
        return _md.markdown(text, extensions=["extra", "toc",
                                              "sane_lists"])  # safe mode not needed if content trusted in admin
    # fallback: preserve newlines
    return str(text).replace("\n", "<br>")


# ----------------------------------------------------------------------
# NEW FILTERS FOR ABSOLUTE URLS AND STRING REPLACEMENT
# ----------------------------------------------------------------------

@register.filter
def build_absolute_uri(relative_url, request=None):
    """
    Returns the absolute URI for a given relative URL, essential for SEO tags.
    It relies on CANONICAL_HOST defined in settings.
    Usage: {{ post.cover_image.url|build_absolute_uri }}
    """
    if hasattr(settings, 'CANONICAL_HOST') and settings.CANONICAL_HOST:
        # Determine scheme (https in production, http in local debug)
        scheme = 'https' if not settings.DEBUG else 'http'

        # Ensure the URL is just the path part before joining
        path_part = relative_url
        if path_part and not path_part.startswith('/'):
            path_part = '/' + path_part

        return f"{scheme}://{settings.CANONICAL_HOST}{path_part}"

    # Fallback to the original URL if unable to build absolute
    return relative_url


@register.filter
def replace(value, arg):
    """
    Replaces a string (arg[0]) with another string (arg[1]) in value.
    This is used in detail.html for replacing 'http:' with 'https:' for og:image.
    Usage: {{ value|replace:'old,new' }}
    """
    if isinstance(arg, str):
        args = arg.split(',')
        if len(args) == 2:
            return value.replace(args[0], args[1])
    return value
