from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from functools import wraps

from core.models import Student, Teacher, User


def admin_required(view_func):
    """Decorator to ensure user is an admin."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin:
            messages.error(request, 'ليس لديك صلاحية الوصول لهذه الصفحة')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@admin_required
def dashboard(request):
    """Admin dashboard with summary statistics."""
    context = {
        'total_students': Student.objects.count(),
        'total_teachers': Teacher.objects.count(),
        'total_users': User.objects.count(),
    }
    return render(request, 'admin_portal/dashboard.html', context)
