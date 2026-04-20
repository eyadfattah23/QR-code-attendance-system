from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from functools import wraps

from core.models import Student, Teacher, StudentTeacherLink


def teacher_required(view_func):
    """Decorator to ensure user is a teacher."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_teacher:
            messages.error(request, 'ليس لديك صلاحية الوصول لهذه الصفحة')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@teacher_required
def dashboard(request):
    """Teacher dashboard showing their students."""
    try:
        teacher = Teacher.objects.get(user=request.user)
        student_links = StudentTeacherLink.objects.filter(
            teacher=teacher,
            is_active=True
        ).select_related('student')
        students = [link.student for link in student_links]
    except Teacher.DoesNotExist:
        students = []
        messages.warning(request, 'لم يتم ربط حسابك بملف معلم')

    context = {
        'students': students,
        'total_students': len(students),
    }
    return render(request, 'teacher_portal/dashboard.html', context)
