from django import template

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
