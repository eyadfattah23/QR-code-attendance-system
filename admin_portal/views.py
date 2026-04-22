from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.timezone import localdate
from django.db import models
from functools import wraps

from core.models import Student, Teacher, User
from attendance.models import StudentAttendanceRecord, TeacherAttendanceRecord


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
    today = localdate()

    today_student_attendance = StudentAttendanceRecord.objects.filter(
        date=today)
    today_teacher_attendance = TeacherAttendanceRecord.objects.filter(
        date=today)

    context = {
        'total_students': Student.objects.count(),
        'total_teachers': Teacher.objects.count(),
        'total_users': User.objects.count(),
        'today_student_attendance_count': today_student_attendance.count(),
        'today_teacher_attendance_count': today_teacher_attendance.count(),
        'today_substitute_count': today_student_attendance.filter(
            original_teacher__isnull=False,
            assigned_teacher__isnull=False,
        ).exclude(original_teacher=models.F('assigned_teacher')).count(),
        'today_missing_photos_count': today_student_attendance.filter(
            daily_photo__isnull=True
        ).count(),
        'today': today,
    }
    return render(request, 'admin_portal/dashboard.html', context)
