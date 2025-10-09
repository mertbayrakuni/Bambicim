# core/templatetags/search_extras.py
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def highlight(text: str, query_or_tokens):
    if not text:
        return ""
    # accept either the raw query string or a tokens list
    tokens = query_or_tokens
    if isinstance(query_or_tokens, str):
        tokens = [t for t in re.findall(r"\w+", query_or_tokens.lower()) if len(t) >= 3]
    if not tokens:
        return escape(text)

    def repl(m):
        return f"<mark>{m.group(0)}</mark>"

    out = escape(text)
    # Replace each token case-insensitively; keep it simple and safe
    for t in sorted(set(tokens), key=len, reverse=True):
        out = re.sub(rf"(?i)\b{re.escape(t)}\b", repl, out)
    return mark_safe(out)
