from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg
from django.http import HttpResponse
from django.utils.timezone import localdate, localtime
from django.views.decorators.http import require_http_methods
from functools import wraps
import uuid
import openpyxl

from django.db.models import Avg, Q

from core.models import Student, Teacher, StudentTeacherLink
from attendance.models import StudentAttendanceRecord
from admin_portal.models import AuditLog


def _log_audit(request, action, object_type, object_repr):
    """Create an AuditLog entry for a delete or edit action."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '')
    AuditLog.objects.create(
        action=action,
        actor_phone=request.user.phone,
        ip_address=ip,
        object_type=object_type,
        object_repr=str(object_repr)[:255],
    )


def teacher_required(view_func):
    """Decorator to ensure user is a teacher or a supervisor who has selected a teacher."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_teacher:
            return view_func(request, *args, **kwargs)
        if request.user.is_supervisor:
            if not request.session.get('supervisor_teacher_id'):
                return redirect('supervisor_portal:dashboard')
            return view_func(request, *args, **kwargs)
        messages.error(request, 'ليس لديك صلاحية الوصول لهذه الصفحة')
        return redirect('dashboard')
    return wrapper


def get_acting_teacher(request):
    """Return the Teacher this request is acting as.

    For teachers: their own Teacher profile.
    For supervisors: the teacher stored in session.
    Returns None if the teacher cannot be resolved.
    """
    if request.user.is_supervisor:
        pk = request.session.get('supervisor_teacher_id')
        if not pk:
            return None
        try:
            return Teacher.objects.get(pk=pk)
        except Teacher.DoesNotExist:
            return None
    try:
        return Teacher.objects.get(user=request.user)
    except Teacher.DoesNotExist:
        return None


@teacher_required
def dashboard(request):
    """Teacher dashboard showing their students."""
    today = localdate()
    sort = request.GET.get('sort', '')

    teacher = get_acting_teacher(request)
    try:
        if teacher is None:
            raise Teacher.DoesNotExist

        linked_student_ids = list(
            StudentTeacherLink.objects.filter(teacher=teacher).values_list('student_id', flat=True)
        )
        assigned_student_ids = list(
            StudentAttendanceRecord.objects.filter(assigned_teacher=teacher, date=today).values_list('student_id', flat=True)
        )
        all_student_ids = set(linked_student_ids + assigned_student_ids)

        students = list(Student.objects.filter(id__in=all_student_ids))

        today_attendance = StudentAttendanceRecord.objects.filter(
            student__in=students,
            date=today,
        ).select_related('assigned_teacher', 'original_teacher')
        attendance_by_student_id = {
            record.student_id: record for record in today_attendance
        }

        student_ids = [s.id for s in students]
        avg_ratings = {}
        if student_ids:
            avg_ratings = dict(
                StudentAttendanceRecord.objects
                .filter(student_id__in=student_ids)
                .values('student_id')
                .annotate(avg=Avg('rating'))
                .values_list('student_id', 'avg')
            )

        student_rows = []
        for student in students:
            attendance = attendance_by_student_id.get(student.id)
            student_rows.append({
                'student': student,
                'attendance': attendance,
                'is_attended': attendance is not None,
                'avg_rating': avg_ratings.get(student.id),
            })

        if sort == 'avg_rating_desc':
            student_rows.sort(key=lambda r: r['avg_rating'] or 0, reverse=True)
        elif sort == 'avg_rating_asc':
            student_rows.sort(key=lambda r: r['avg_rating'] or 0)
        elif sort == 'name_asc':
            student_rows.sort(key=lambda r: r['student'].full_name)
        elif sort == 'name_desc':
            student_rows.sort(
                key=lambda r: r['student'].full_name, reverse=True)
        elif sort == 'attended_first':
            student_rows.sort(key=lambda r: not r['is_attended'])
        elif sort == 'absent_first':
            student_rows.sort(key=lambda r: r['is_attended'])
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
        'sort': sort,
        'acting_teacher': teacher,
    }
    return render(request, 'teacher_portal/dashboard.html', context)


@teacher_required
@require_http_methods(["POST"])
def teacher_scan(request):
    """Process attendance scans for teacher's linked students only."""
    teacher = get_acting_teacher(request)
    try:
        if teacher is None:
            raise Teacher.DoesNotExist

        today = localdate()

        linked_student_ids = list(
            StudentTeacherLink.objects.filter(teacher=teacher).values_list('student_id', flat=True)
        )
        assigned_student_ids = list(
            StudentAttendanceRecord.objects.filter(assigned_teacher=teacher, date=today).values_list('student_id', flat=True)
        )
        allowed_student_ids = set(linked_student_ids + assigned_student_ids)

        scanned_codes = request.POST.get("scanned_codes", "").strip()
        codes = [line.strip()
                 for line in scanned_codes.splitlines() if line.strip()]

        if not codes:
            messages.warning(
                request, "الرجاء إدخال رمز واحد على الأقل قبل الإرسال")
            return redirect('teacher_portal:dashboard')

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

                if any_student.id not in allowed_student_ids:
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

                if any_student.id not in allowed_student_ids:
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


@teacher_required
def student_history(request, pk):
    """Full attendance history for a student linked to the requesting teacher."""
    teacher = get_acting_teacher(request)
    if teacher is None:
        messages.error(request, 'لم يتم ربط حسابك بملف معلم')
        return redirect('teacher_portal:dashboard')

    students = Student.objects.filter(
        Q(teacher_links__teacher=teacher) | Q(attendance_records__assigned_teacher=teacher),
        pk=pk
    ).distinct()
    student = get_object_or_404(students)

    records = (
        StudentAttendanceRecord.objects
        .filter(student=student)
        .select_related('assigned_teacher', 'original_teacher')
        .order_by('-date', '-check_in_time')
    )
    total_records = records.count()
    avg_rating = records.aggregate(avg=Avg('rating'))['avg']

    return render(request, 'teacher_portal/student_history.html', {
        'student': student,
        'records': records,
        'total_records': total_records,
        'avg_rating': avg_rating,
    })


@teacher_required
@require_http_methods(["GET", "POST"])
def upload_photo(request, pk):
    """Upload or replace the daily notebook photo for an attendance record."""
    teacher = get_acting_teacher(request)
    if teacher is None:
        messages.error(request, 'لم يتم ربط حسابك بملف معلم')
        return redirect('teacher_portal:dashboard')

    records = StudentAttendanceRecord.objects.filter(
        Q(student__teacher_links__teacher=teacher) | Q(assigned_teacher=teacher),
        pk=pk
    ).distinct()
    record = get_object_or_404(records)

    if request.method == 'POST':
        photo_field = request.POST.get('photo_field')
        if photo_field not in ('homework_photo', 'test_photo'):
            messages.error(request, 'حقل الصورة غير صالح')
            return redirect('teacher_portal:upload_photo', pk=pk)
            
        photo = request.FILES.get(photo_field)
        if not photo:
            messages.error(request, 'الرجاء اختيار صورة')
            return redirect('teacher_portal:upload_photo', pk=pk)

        allowed_types = {'image/jpeg', 'image/png', 'image/webp'}
        if photo.content_type not in allowed_types:
            messages.error(
                request, 'نوع الملف غير مدعوم. يُقبل JPEG أو PNG أو WebP فقط')
            return redirect('teacher_portal:upload_photo', pk=pk)

        if photo.size > 2 * 1024 * 1024:  # 2MB hard server-side cap
            messages.error(
                request, 'حجم الملف كبير جداً. الحد الأقصى 2MB (يُرجى الضغط من المتصفح)')
            return redirect('teacher_portal:upload_photo', pk=pk)

        current_photo = getattr(record, photo_field)
        # Delete old file from storage before replacing
        if current_photo:
            current_photo.delete(save=False)

        setattr(record, photo_field, photo)
        record.save(update_fields=[photo_field])
        _log_audit(request, AuditLog.Action.EDIT, 'سجل حضور طالب (صورة)',
                   f'{record.student.full_name} — {record.date}')
        messages.success(request, 'تم رفع الصورة بنجاح')
        return redirect('teacher_portal:dashboard')

    return render(request, 'teacher_portal/upload_photo.html', {
        'record': record,
        'student': record.student,
    })


@teacher_required
@require_http_methods(["GET", "POST"])
def edit_record_note(request, pk):
    """Add or edit the teacher note on a single attendance record."""
    teacher = get_acting_teacher(request)
    if teacher is None:
        messages.error(request, 'لم يتم ربط حسابك بملف معلم')
        return redirect('teacher_portal:dashboard')

    records = StudentAttendanceRecord.objects.filter(
        Q(student__teacher_links__teacher=teacher) | Q(assigned_teacher=teacher),
        pk=pk
    ).distinct()
    record = get_object_or_404(records)

    if request.method == 'POST':
        note = request.POST.get('teacher_note', '').strip()
        record.teacher_note = note
        record.save(update_fields=['teacher_note'])
        _log_audit(request, AuditLog.Action.EDIT, 'سجل حضور طالب (ملاحظة)',
                   f'{record.student.full_name} — {record.date}')
        messages.success(request, 'تم حفظ الملاحظة بنجاح')
        return redirect('teacher_portal:dashboard')

    return render(request, 'teacher_portal/edit_record_note.html', {
        'record': record,
        'student': record.student,
    })


@teacher_required
def export_attendance(request):
    """Export today's attendance list for the teacher's linked students as Excel."""
    today = localdate()
    teacher = get_acting_teacher(request)
    if teacher is None:
        messages.error(request, 'لم يتم ربط حسابك بملف معلم')
        return redirect('teacher_portal:dashboard')

    linked_student_ids = list(
        StudentTeacherLink.objects.filter(teacher=teacher).values_list('student_id', flat=True)
    )
    assigned_student_ids = list(
        StudentAttendanceRecord.objects.filter(assigned_teacher=teacher, date=today).values_list('student_id', flat=True)
    )
    all_student_ids = set(linked_student_ids + assigned_student_ids)

    students = list(Student.objects.filter(id__in=all_student_ids))

    today_attendance = StudentAttendanceRecord.objects.filter(
        student__in=students, date=today
    )
    attendance_by_id = {r.student_id: r for r in today_attendance}

    student_ids = [s.id for s in students]
    avg_ratings = {}
    if student_ids:
        avg_ratings = dict(
            StudentAttendanceRecord.objects
            .filter(student_id__in=student_ids)
            .values('student_id')
            .annotate(avg=Avg('rating'))
            .values_list('student_id', 'avg')
        )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = str(today)
    ws.append(['اسم الطالب', 'الصف', 'حالة الحضور', 'وقت الحضور',
              'التقييم', 'متوسط التقييم', 'الملاحظة'])

    for student in students:
        att = attendance_by_id.get(student.id)
        avg = avg_ratings.get(student.id)
        ws.append([
            student.full_name,
            student.grade or '',
            'حضر' if att else 'لم يسجل',
            localtime(att.check_in_time).strftime(
                '%H:%M') if att and att.check_in_time else '',
            att.rating if att else '',
            round(avg, 1) if avg is not None else '',
            att.teacher_note if att else '',
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="attendance_{today}.xlsx"'
    wb.save(response)
    return response
