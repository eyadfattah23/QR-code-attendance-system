"""Shared list filters."""


def get_is_teacher_filter(request):
    """Return the `is_teacher` GET param normalised to '1', '0' or ''."""
    value = request.GET.get('is_teacher', '').strip()
    return value if value in ('1', '0') else ''


def apply_is_teacher_filter(qs, value, field='is_teacher'):
    """Filter `qs` by the student is_teacher flag ('1' = only, '0' = exclude)."""
    if value == '1':
        return qs.filter(**{field: True})
    if value == '0':
        return qs.filter(**{field: False})
    return qs
