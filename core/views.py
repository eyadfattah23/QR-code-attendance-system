"""
Authentication views for the QR Attendance System.

This module handles user authentication including login, logout,
and dashboard redirection based on user roles.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Handle user login.

    GET: Display the login form
    POST: Process login credentials and authenticate user

    Redirects authenticated users to dashboard.
    On successful login, redirects to 'next' parameter or dashboard.
    """
    # Redirect if already authenticated
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request=request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # Welcome message
            display_name = user.get_full_name() or user.phone
            messages.success(request, f'مرحباً {display_name}')

            # Handle 'next' redirect safely
            next_url = request.GET.get('next') or request.POST.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure()
            ):
                return redirect(next_url)

            return redirect('dashboard')
    else:
        form = LoginForm()

    return render(request, 'auth/login.html', {
        'form': form,
        'next': request.GET.get('next', ''),
    })


@never_cache
@require_http_methods(["GET", "POST"])
def logout_view(request):
    """
    Handle user logout.

    Logs out the user (both GET and POST for convenience).
    Displays success message and redirects to login page.
    """
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, 'تم تسجيل الخروج بنجاح')

    return redirect('login')


@login_required
@never_cache
def dashboard_redirect(request):
    """
    Redirect user to appropriate dashboard based on role.

    Admins are redirected to admin_portal:dashboard
    Teachers are redirected to teacher_portal:dashboard
    Users without proper roles see a warning and are redirected to login.
    """
    user = request.user

    if user.is_admin:
        return redirect('admin_portal:dashboard')
    elif user.is_teacher:
        return redirect('teacher_portal:dashboard')
    else:
        # Fallback - shouldn't happen with proper role setup
        messages.warning(
            request, 'لم يتم تحديد صلاحيات المستخدم. يرجى التواصل مع المسؤول')
        logout(request)
        return redirect('login')
