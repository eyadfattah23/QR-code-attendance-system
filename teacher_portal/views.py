from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.timezone import localdate, localtime
from django.views.decorators.http import require_http_methods
from functools import wraps
import uuid

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


@teacher_required
@require_http_methods(["POST"])
def teacher_scan(request):
    """Process attendance scans for teacher's linked students only."""
    try:
        teacher = Teacher.objects.get(user=request.user)

        # Get teacher's linked students
        student_links = StudentTeacherLink.objects.filter(
            teacher=teacher
        ).select_related('student')
        linked_student_ids = set(link.student_id for link in student_links)

        # Process scanned codes
        scanned_codes = request.POST.get("scanned_codes", "").strip()
        codes = [line.strip()
                 for line in scanned_codes.splitlines() if line.strip()]

        today = localdate()
        results = []

        for raw_code in codes:
            student = None

            try:
                # Try UUID lookup
                code_uuid = uuid.UUID(raw_code)
                student = Student.objects.filter(
                    id=code_uuid,
                    id__in=linked_student_ids
                ).first()
            except ValueError:
                # Try student_code or national_id lookup
                lookup = raw_code.strip().upper()
                student = Student.objects.filter(
                    student_code__iexact=lookup,
                    id__in=linked_student_ids
                ).first()
                if student is None:
                    student = Student.objects.filter(
                        national_id__iexact=lookup,
                        id__in=linked_student_ids
                    ).first()

            if student is not None:
                primary_link = (
                    StudentTeacherLink.objects.filter(student=student)
                    .order_by("-is_primary", "created_at")
                    .select_related("teacher")
                    .first()
                )
                original_teacher = primary_link.teacher if primary_link else None

                student_record, created = StudentAttendanceRecord.objects.get_or_create(
                    student=student,
                    date=today,
                    defaults={
                        "check_in_time": localtime(),
                        "recorded_by": request.user,
                        "original_teacher": original_teacher,
                        "assigned_teacher": original_teacher,
                        "substitute_note": "",
                        "rating": 6,
                    },
                )

                if created:
                    messages.success(
                        request,
                        f"{student.full_name} - تم تسجيل الحضور بنجاح"
                    )
                else:
                    messages.warning(
                        request,
                        f"{student.full_name} - مسجل مسبقاً الساعة {student_record.check_in_time.strftime('%H:%M')}"
                    )
            else:
                messages.error(request, f"الطالب غير مرتبط بك: {raw_code}")

    except Teacher.DoesNotExist:
        messages.error(request, 'لم يتم ربط حسابك بملف معلم')

    return redirect('teacher_portal:dashboard')
