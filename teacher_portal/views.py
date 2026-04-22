from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.timezone import localdate
from functools import wraps

from core.models import Student, Teacher, StudentTeacherLink
from attendance.models import StudentAttendanceRecord


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
    today = localdate()

    try:
        teacher = Teacher.objects.get(user=request.user)
        student_links = StudentTeacherLink.objects.filter(
            teacher=teacher
        ).select_related('student')
        students = [link.student for link in student_links]

        today_attendance = StudentAttendanceRecord.objects.filter(
            student__in=students,
            date=today,
        ).select_related('assigned_teacher', 'original_teacher')
        attendance_by_student_id = {
            record.student_id: record for record in today_attendance
        }

        student_rows = []
        for student in students:
            attendance = attendance_by_student_id.get(student.id)
            student_rows.append({
                'student': student,
                'attendance': attendance,
                'is_attended': attendance is not None,
            })
    except Teacher.DoesNotExist:
        students = []
        student_rows = []
        messages.warning(request, 'لم يتم ربط حسابك بملف معلم')

    attended_count = sum(1 for row in student_rows if row['is_attended'])

    context = {
        'students': students,
        'student_rows': student_rows,
        'total_students': len(students),
        'attended_count': attended_count,
        'today': today,
    }
    return render(request, 'teacher_portal/dashboard.html', context)
