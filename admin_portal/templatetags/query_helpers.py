"""Custom template tags for query-string manipulation in pagination links."""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """
    Build a URL query string from the current request's GET parameters,
    replacing/adding any parameters passed as keyword arguments.

    Usage in templates:
        <a href="?{% querystring page=3 %}">Page 3</a>

    This preserves ALL existing query parameters (filters, sort, search, etc.)
    and only overrides the ones you explicitly pass. Parameters set to an
    empty string are removed from the output.
    """
    request = context.get('request')
    if request is None:
        return ''

    # Copy existing GET params (mutable)
    params = request.GET.copy()

    # Override / add / remove specified params
    for key, value in kwargs.items():
        if value == '' or value is None:
            params.pop(key, None)
        else:
            params[key] = str(value)

    return params.urlencode()
