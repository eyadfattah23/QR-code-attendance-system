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

        linked_student_ids = set(
            StudentTeacherLink.objects.filter(teacher=teacher)
            .values_list('student_id', flat=True)
        )

        scanned_codes = request.POST.get("scanned_codes", "").strip()
        codes = [line.strip()
                 for line in scanned_codes.splitlines() if line.strip()]

        if not codes:
            messages.warning(
                request, "الرجاء إدخال رمز واحد على الأقل قبل الإرسال")
            return redirect('teacher_portal:dashboard')

        today = localdate()

        for raw_code in codes:
            student = None

            try:
                code_uuid = uuid.UUID(raw_code)

                # Teacher QR card → teacher attendance is recorded by admin only
                if Teacher.objects.filter(id=code_uuid).exists():
                    messages.warning(
                        request,
                        f"تسجيل حضور المعلمين يتم من قِبَل المسؤول فقط - الرمز: {raw_code}",
                    )
                    continue

                any_student = Student.objects.filter(id=code_uuid).first()
                if any_student is None:
                    messages.error(
                        request, f"لم يتم العثور على هذا الرمز: {raw_code}")
                    continue

                if any_student.id not in linked_student_ids:
                    messages.error(
                        request, f"{any_student.full_name} - ليس ضمن قائمة طلابك")
                    continue

                student = any_student

            except ValueError:
                lookup = raw_code.strip().upper()
                any_student = (
                    Student.objects.filter(student_code__iexact=lookup).first()
                    or Student.objects.filter(national_id__iexact=lookup).first()
                )
                if any_student is None:
                    messages.error(
                        request, f"لم يتم العثور على هذا الرمز: {raw_code}")
                    continue

                if any_student.id not in linked_student_ids:
                    messages.error(
                        request, f"{any_student.full_name} - ليس ضمن قائمة طلابك")
                    continue

                student = any_student

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
                    f"{student.full_name} - تم تسجيل الحضور بنجاح",
                )
            else:
                messages.warning(
                    request,
                    f"{student.full_name} - مسجل مسبقاً الساعة "
                    f"{student_record.check_in_time.strftime('%H:%M')}",
                )

    except Teacher.DoesNotExist:
        messages.error(request, 'لم يتم ربط حسابك بملف معلم')

    return redirect('teacher_portal:dashboard')
