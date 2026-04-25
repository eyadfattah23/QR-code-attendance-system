import io

import openpyxl
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.timezone import localdate
from django.views.decorators.http import require_http_methods
from functools import wraps

from core.models import Student, Teacher, User
from attendance.models import StudentAttendanceRecord, TeacherAttendanceRecord
from .forms import StudentForm, TeacherForm


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
            models.Q(daily_photo__isnull=True) | models.Q(daily_photo='')
        ).count(),
        'today': today,
    }
    return render(request, 'admin_portal/dashboard.html', context)


# ---------------------------------------------------------------------------
# Student management
# ---------------------------------------------------------------------------

@admin_required
def student_list(request):
    """Paginated student list with search and grade filter."""
    q = request.GET.get('q', '').strip()
    grade_filter = request.GET.get('grade', '').strip()

    qs = Student.objects.all()
    if q:
        qs = qs.filter(
            Q(full_name__icontains=q)
            | Q(national_id__icontains=q)
            | Q(student_code__icontains=q)
        )
    if grade_filter:
        qs = qs.filter(grade=grade_filter)

    grades = (
        Student.objects
        .exclude(grade__isnull=True)
        .exclude(grade='')
        .values_list('grade', flat=True)
        .distinct()
        .order_by('grade')
    )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin_portal/students.html', {
        'page_obj': page_obj,
        'q': q,
        'grade_filter': grade_filter,
        'grades': grades,
        'total_count': qs.count(),
    })


@admin_required
def student_create(request):
    """Create a new student."""
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            messages.success(
                request, f'تم إضافة الطالب "{student.full_name}" بنجاح')
            return redirect('admin_portal:student_list')
    else:
        form = StudentForm()

    return render(request, 'admin_portal/student_form.html', {
        'form': form,
        'title': 'إضافة طالب جديد',
        'submit_label': 'إضافة',
    })


@admin_required
def student_edit(request, pk):
    """Edit an existing student."""
    student = get_object_or_404(Student, pk=pk)

    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(
                request, f'تم تحديث بيانات "{student.full_name}" بنجاح')
            return redirect('admin_portal:student_list')
    else:
        form = StudentForm(instance=student)

    return render(request, 'admin_portal/student_form.html', {
        'form': form,
        'student': student,
        'title': f'تعديل: {student.full_name}',
        'submit_label': 'حفظ التغييرات',
    })


@admin_required
@require_http_methods(['POST'])
def student_delete(request, pk):
    """Delete a student (POST only)."""
    student = get_object_or_404(Student, pk=pk)
    name = student.full_name
    student.delete()
    messages.success(request, f'تم حذف الطالب "{name}" بنجاح')
    return redirect('admin_portal:student_list')


@admin_required
@require_http_methods(['POST'])
def student_import(request):
    """Bulk-import students from an uploaded Excel file."""
    excel_file = request.FILES.get('excel_file')
    if not excel_file:
        messages.error(request, 'الرجاء اختيار ملف Excel')
        return redirect('admin_portal:student_list')

    if not excel_file.name.lower().endswith(('.xlsx', '.xlsm', '.xltx', '.xltm')):
        messages.error(request, 'الملف يجب أن يكون بصيغة Excel (.xlsx)')
        return redirect('admin_portal:student_list')

    try:
        wb = openpyxl.load_workbook(excel_file, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except Exception:
        messages.error(request, 'تعذّر قراءة الملف. تأكد أنه ملف Excel صالح.')
        return redirect('admin_portal:student_list')

    if len(rows) < 2:
        messages.warning(request, 'الملف لا يحتوي على بيانات')
        return redirect('admin_portal:student_list')

    # Normalise header row
    headers = [str(h).strip().lower()
               if h is not None else '' for h in rows[0]]
    if not {'full_name', 'national_id'}.issubset(set(headers)):
        messages.error(
            request, 'يجب أن يحتوي الملف على أعمدة: full_name و national_id')
        return redirect('admin_portal:student_list')

    col = {h: i for i, h in enumerate(headers) if h}

    created = skipped = 0
    error_msgs = []

    for row_num, row in enumerate(rows[1:], start=2):
        def _cell(name, _row=row):
            idx = col.get(name)
            if idx is None or idx >= len(_row):
                return ''
            return str(_row[idx] or '').strip()

        full_name = _cell('full_name')
        national_id = _cell('national_id')

        # Skip entirely blank rows
        if not full_name and not national_id:
            continue

        if not full_name:
            error_msgs.append(f'الصف {row_num}: الاسم الكامل مطلوب')
            continue
        if not national_id:
            error_msgs.append(f'الصف {row_num}: الرقم القومي مطلوب')
            continue

        if Student.objects.filter(national_id=national_id).exists():
            skipped += 1
            continue

        student_code = _cell('student_code') or None
        grade = _cell('grade') or None

        try:
            Student.objects.create(
                full_name=full_name,
                national_id=national_id,
                student_code=student_code,
                grade=grade,
            )
            created += 1
        except Exception as exc:
            error_msgs.append(f'الصف {row_num}: {exc}')

    # Feedback messages
    if created:
        messages.success(request, f'تمت إضافة {created} طالب بنجاح')
    if skipped:
        messages.warning(
            request, f'تم تخطي {skipped} سجل مكرر (الرقم القومي موجود مسبقاً)')
    if error_msgs:
        preview = ' | '.join(error_msgs[:5])
        if len(error_msgs) > 5:
            preview += f' ... (+{len(error_msgs) - 5} أخطاء أخرى)'
        messages.error(
            request, f'{len(error_msgs)} خطأ أثناء الاستيراد: {preview}')
    if not created and not skipped and not error_msgs:
        messages.info(request, 'لم يتم العثور على بيانات جديدة للاستيراد')

    return redirect('admin_portal:student_list')


@admin_required
@require_http_methods(['GET'])
def student_import_template(request):
    """Return a blank Excel template for bulk student import."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Students'
    ws.append(['full_name', 'national_id', 'student_code', 'grade'])
    ws.append(['أحمد محمد علي', '12345678901234', 'STU001', 'السنة الأولى'])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="students_import_template.xlsx"'
    return response


# ---------------------------------------------------------------------------
# Teacher management
# ---------------------------------------------------------------------------

@admin_required
def teacher_list(request):
    """Paginated teacher list with name / phone / subject search."""
    q = request.GET.get('q', '').strip()

    qs = Teacher.objects.select_related('user').all()
    if q:
        qs = qs.filter(
            Q(full_name__icontains=q)
            | Q(subject__icontains=q)
            | Q(user__phone__icontains=q)
        )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin_portal/teachers.html', {
        'page_obj': page_obj,
        'q': q,
        'total_count': qs.count(),
    })


@admin_required
def teacher_create(request):
    """Create a new teacher with a linked user account."""
    if request.method == 'POST':
        form = TeacherForm(request.POST)
        if form.is_valid():
            teacher = form.save()
            messages.success(
                request, f'تم إضافة المعلم "{teacher.full_name}" بنجاح')
            return redirect('admin_portal:teacher_list')
    else:
        form = TeacherForm()

    return render(request, 'admin_portal/teacher_form.html', {
        'form': form,
        'title': 'إضافة معلم جديد',
        'submit_label': 'إضافة',
    })


@admin_required
def teacher_edit(request, pk):
    """Edit an existing teacher and their linked user account."""
    teacher = get_object_or_404(Teacher.objects.select_related('user'), pk=pk)

    if request.method == 'POST':
        form = TeacherForm(request.POST, instance=teacher)
        if form.is_valid():
            form.save()
            messages.success(
                request, f'تم تحديث بيانات "{teacher.full_name}" بنجاح')
            return redirect('admin_portal:teacher_list')
    else:
        form = TeacherForm(
            initial={
                'full_name': teacher.full_name,
                'subject': teacher.subject or '',
                'phone': teacher.user.phone,
                'first_name': teacher.user.first_name,
                'last_name': teacher.user.last_name,
            },
            instance=teacher,
        )

    return render(request, 'admin_portal/teacher_form.html', {
        'form': form,
        'teacher': teacher,
        'title': f'تعديل: {teacher.full_name}',
        'submit_label': 'حفظ التغييرات',
    })


@admin_required
@require_http_methods(['POST'])
def teacher_delete(request, pk):
    """Delete a teacher (and their user account) — POST only."""
    teacher = get_object_or_404(Teacher, pk=pk)
    name = teacher.full_name
    # Deleting the user cascades to the Teacher profile
    teacher.user.delete()
    messages.success(request, f'تم حذف المعلم "{name}" بنجاح')
    return redirect('admin_portal:teacher_list')
