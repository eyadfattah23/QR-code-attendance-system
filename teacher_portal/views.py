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

from django.db import IntegrityError
from django.db.models import Avg, Q

from core.models import Student, Teacher, StudentTeacherLink
from core.filters import get_is_teacher_filter
from attendance.models import StudentAttendanceRecord
from admin_portal.models import AuditLog


def _log_audit(request, action, object_type, object_repr):
    """Create an AuditLog entry for a delete or edit action."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = forwarded.split(',')[0].strip(
    ) if forwarded else request.META.get('REMOTE_ADDR', '')
    AuditLog.objects.create(
        action=action,
        actor_phone=request.user.phone,
        ip_address=ip,
        object_type=object_type,
        object_repr=str(object_repr)[:255],
    )


def teacher_required(view_func):
    """Decorator to ensure user is a teacher, a supervisor, an admin, or an assistant."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_teacher:
            return view_func(request, *args, **kwargs)
        if request.user.is_supervisor or request.user.is_admin:
            teacher_pk = request.session.get('supervisor_teacher_id')
            if not teacher_pk:
                return redirect('supervisor_portal:dashboard')
            if not Teacher.objects.filter(pk=teacher_pk, is_active=True).exists():
                # Selected teacher was deleted/deactivated since it was chosen.
                request.session.pop('supervisor_teacher_id', None)
                messages.warning(request, 'هذا المعلم لم يعد نشطاً')
                return redirect('supervisor_portal:dashboard')
            return view_func(request, *args, **kwargs)
        if request.user.is_assistant:
            if not request.session.get('assistant_teacher_id'):
                return redirect('assistant_portal:dashboard')
            return view_func(request, *args, **kwargs)
        messages.error(request, 'ليس لديك صلاحية الوصول لهذه الصفحة')
        return redirect('dashboard')
    return wrapper


def get_acting_teacher(request):
    """Return the Teacher this request is acting as.

    For teachers: their own Teacher profile.
    For supervisors and admins: the teacher stored in session.
    For assistants: the teacher stored in session, IF the link still exists.
    Returns None if the teacher cannot be resolved.
    """
    if request.user.is_supervisor or request.user.is_admin:
        pk = request.session.get('supervisor_teacher_id')
        if not pk:
            return None
        try:
            return Teacher.objects.get(pk=pk, is_active=True)
        except Teacher.DoesNotExist:
            return None
            
    if request.user.is_assistant:
        pk = request.session.get('assistant_teacher_id')
        if not pk:
            return None
        try:
            teacher = Teacher.objects.get(pk=pk, is_active=True)
            # CRITICAL: Re-verify link exists to prevent stale-session access
            from core.models import AssistantTeacherLink
            if AssistantTeacherLink.objects.filter(user=request.user, teacher=teacher).exists():
                return teacher
            return None
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
    is_teacher_filter = get_is_teacher_filter(request)

    teacher = get_acting_teacher(request)
    try:
        if teacher is None:
            raise Teacher.DoesNotExist

        linked_student_ids = list(
            StudentTeacherLink.objects.filter(
                teacher=teacher).values_list('student_id', flat=True)
        )
        assigned_student_ids = list(
            StudentAttendanceRecord.objects.filter(
                assigned_teacher=teacher, date=today).values_list('student_id', flat=True)
        )
        all_student_ids = set(linked_student_ids + assigned_student_ids)

        students = list(Student.objects.filter(id__in=all_student_ids))

        today_attendance = StudentAttendanceRecord.objects.filter(
            Q(original_teacher=teacher) | Q(assigned_teacher=teacher),
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
                .filter(
                    Q(original_teacher=teacher) | Q(assigned_teacher=teacher),
                    student_id__in=student_ids,
                )
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

        # Students who are also teachers always come first (stable sort keeps
        # the chosen ordering within each group).
        student_rows.sort(key=lambda r: not r['student'].is_teacher)

        if is_teacher_filter:
            want = is_teacher_filter == '1'
            student_rows = [
                r for r in student_rows if r['student'].is_teacher == want]
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
        'is_teacher_filter': is_teacher_filter,
        'acting_teacher': teacher,
        'scan_results': request.session.pop('teacher_scan_results', []),
    }
    return render(request, 'teacher_portal/dashboard.html', context)


@teacher_required
@require_http_methods(["POST"])
def teacher_scan(request):
    """Process attendance scans for teacher's linked students only.

    Results (with student image, like the admin scan station) are stored in the
    session and rendered on the dashboard after the redirect.
    """
    teacher = get_acting_teacher(request)
    results = []
    icons = {
        'success': 'bi-check-circle-fill',
        'warning': 'bi-exclamation-triangle-fill',
        'danger': 'bi-x-circle-fill',
    }

    def add_result(row_class, message, student=None, label=None):
        results.append({
            'row_class': row_class,
            'icon': icons[row_class],
            'label': student.full_name if student else (label or 'خطأ'),
            'message': message,
            'has_image': student is not None,
            'image_url': student.image.url if student and student.image else None,
        })

    try:
        if teacher is None:
            raise Teacher.DoesNotExist

        today = localdate()

        linked_student_ids = list(
            StudentTeacherLink.objects.filter(
                teacher=teacher).values_list('student_id', flat=True)
        )
        assigned_student_ids = list(
            StudentAttendanceRecord.objects.filter(
                assigned_teacher=teacher, date=today).values_list('student_id', flat=True)
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
                    add_result(
                        'warning',
                        f"تسجيل حضور المعلمين يتم من قِبَل المسؤول فقط - الرمز: {raw_code}",
                        label='بطاقة معلم',
                    )
                    continue

                any_student = Student.objects.filter(id=code_uuid).first()
                if any_student is None:
                    add_result('danger', f"لم يتم العثور على هذا الرمز: {raw_code}")
                    continue

                if any_student.id not in allowed_student_ids:
                    add_result('danger', 'ليس ضمن قائمة طلابك', any_student)
                    continue

                student = any_student

            except ValueError:
                lookup = raw_code.strip().upper()
                any_student = (
                    Student.objects.filter(student_code__iexact=lookup).first()
                    or Student.objects.filter(national_id__iexact=lookup).first()
                )
                if any_student is None:
                    add_result('danger', f"لم يتم العثور على هذا الرمز: {raw_code}")
                    continue

                if any_student.id not in allowed_student_ids:
                    add_result('danger', 'ليس ضمن قائمة طلابك', any_student)
                    continue

                student = any_student

            try:
                student_record = StudentAttendanceRecord.objects.get(
                    student=student,
                    date=today,
                    original_teacher=teacher,
                )
                if student_record.check_out_time is None:
                    student_record.check_out_time = localtime()
                    student_record.save(update_fields=['check_out_time'])
                    add_result(
                        'success',
                        f"تم تسجيل الانصراف بنجاح (حصة: {teacher.full_name})",
                        student,
                    )
                else:
                    add_result(
                        'warning',
                        f"غادر مسبقاً الساعة "
                        f"{localtime(student_record.check_out_time).strftime('%H:%M')} (حصة: {teacher.full_name})",
                        student,
                    )
            except StudentAttendanceRecord.DoesNotExist:
                try:
                    StudentAttendanceRecord.objects.create(
                        student=student,
                        date=today,
                        check_in_time=localtime(),
                        recorded_by=request.user,
                        original_teacher=teacher,
                        assigned_teacher=teacher,
                        substitute_note="",
                        rating=6,
                    )
                    add_result(
                        'success',
                        f"تم تسجيل الحضور بنجاح (حصة: {teacher.full_name})",
                        student,
                    )
                except IntegrityError:
                    add_result('warning', 'تم تسجيل حضوره للتو من محطة أخرى', student)

    except Teacher.DoesNotExist:
        messages.error(request, 'لم يتم ربط حسابك بملف معلم')

    if results:
        request.session['teacher_scan_results'] = results
    return redirect('teacher_portal:dashboard')


@teacher_required
def student_history(request, pk):
    """Full attendance history for a student linked to the requesting teacher."""
    teacher = get_acting_teacher(request)
    if teacher is None:
        messages.error(request, 'لم يتم ربط حسابك بملف معلم')
        return redirect('teacher_portal:dashboard')

    students = Student.objects.filter(
        Q(teacher_links__teacher=teacher) | Q(
            attendance_records__assigned_teacher=teacher),
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
        return redirect('teacher_portal:upload_photo', pk=pk)

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
        StudentTeacherLink.objects.filter(
            teacher=teacher).values_list('student_id', flat=True)
    )
    assigned_student_ids = list(
        StudentAttendanceRecord.objects.filter(
            assigned_teacher=teacher, date=today).values_list('student_id', flat=True)
    )
    all_student_ids = set(linked_student_ids + assigned_student_ids)

    students = Student.objects.filter(id__in=all_student_ids).order_by(
        '-is_teacher', 'full_name')
    is_teacher_filter = get_is_teacher_filter(request)
    if is_teacher_filter:
        students = students.filter(is_teacher=is_teacher_filter == '1')
    students = list(students)

    today_attendance = StudentAttendanceRecord.objects.filter(
        Q(original_teacher=teacher) | Q(assigned_teacher=teacher),
        student__in=students, date=today,
    )
    attendance_by_id = {r.student_id: r for r in today_attendance}

    student_ids = [s.id for s in students]
    avg_ratings = {}
    if student_ids:
        avg_ratings = dict(
            StudentAttendanceRecord.objects
            .filter(
                Q(original_teacher=teacher) | Q(assigned_teacher=teacher),
                student_id__in=student_ids,
            )
            .values('student_id')
            .annotate(avg=Avg('rating'))
            .values_list('student_id', 'avg')
        )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = str(today)
    ws.append(['اسم الطالب', 'الصف', 'حالة الحضور', 'وقت الحضور',
              'التقييم', 'متوسط التقييم', 'الملاحظة', 'طالب معلم'])

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
            'نعم' if student.is_teacher else 'لا',
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="attendance_{today}.xlsx"'
    wb.save(response)
    return response
