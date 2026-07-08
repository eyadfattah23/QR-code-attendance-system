import base64
import math
from functools import wraps
from io import BytesIO

import qrcode
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

from core.models import Student, Teacher

# Columns to use for each "cards per page" count (portrait A4 optimised)
CARDS_GRID_COLS = {
    1: 1,   # 1×1  → 190×277 mm
    2: 2,   # 2×1  →  95×277 mm
    3: 2,   # 2×2 (1 empty) →  95×138 mm
    4: 2,   # 2×2  →  95×138 mm
    5: 3,   # 3×2 (1 empty) →  63×138 mm
    6: 3,   # 3×2  →  63×138 mm
    7: 3,   # 3×3 (2 empty) →  63× 92 mm
    8: 2,   # 2×4  →  95× 69 mm  (≈ standard ID card)
    9: 3,   # 3×3  →  63× 92 mm
    10: 2,  # 2×5  →  95× 55 mm  (≈ business card)
    11: 3,  # 3×4 (1 empty) →  63× 69 mm
    12: 3,  # 3×4  →  63× 69 mm
}


def admin_required(view_func):
    """Reuse the same admin-only decorator pattern used across portals."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin:
            messages.error(request, 'ليس لديك صلاحية الوصول لهذه الصفحة')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def _generate_qr_base64(data: str) -> str:
    """Return a base64 PNG data URI for *data*."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


@admin_required
def qr_cards_config(request):
    """Step 1 – choose students and cards-per-page, then go to the print page."""
    # Fetch all distinct grades for the filter dropdown
    grades = (
        Student.objects.exclude(grade__isnull=True)
        .exclude(grade='')
        .values_list('grade', flat=True)
        .distinct()
        .order_by('grade')
    )

    if request.method == 'POST':
        student_ids = request.POST.getlist('student_ids')
        cards_per_page = request.POST.get('cards_per_page', '8')

        if not student_ids:
            messages.error(request, 'يرجى اختيار طالب واحد على الأقل.')
        else:
            request.session['qr_student_ids'] = student_ids
            request.session['qr_cards_per_page'] = cards_per_page
            from django.urls import reverse
            return redirect(reverse('qr_generator:qr_cards_print'))

    # GET – render config page with optional grade / name filters
    grade_filter = request.GET.get('grade', '').strip()
    name_filter = request.GET.get('name', '').strip()

    students = Student.objects.all().order_by('grade', 'full_name')
    if grade_filter:
        students = students.filter(grade=grade_filter)
    if name_filter:
        students = students.filter(full_name__icontains=name_filter)

    return render(request, 'qr_generator/config.html', {
        'students': students,
        'grades': grades,
        'grade_filter': grade_filter,
        'name_filter': name_filter,
        'cards_per_page_range': range(1, 13),
    })


@admin_required
def qr_cards_print(request):
    """Step 2 – render a printable A4 page (or multiple pages) with QR cards."""
    student_ids = request.session.pop('qr_student_ids', None) or request.GET.getlist('sid')
    try:
        cpp_raw = request.session.pop('qr_cards_per_page', None) or request.GET.get('cpp', 8)
        cards_per_page = max(1, min(12, int(cpp_raw)))
    except (ValueError, TypeError):
        cards_per_page = 8

    students = Student.objects.filter(id__in=student_ids).order_by('grade', 'full_name')

    # Build list of (student, qr_data_uri) pairs
    cards = [
        {'student': s, 'qr': _generate_qr_base64(str(s.id))}
        for s in students
    ]

    cols = CARDS_GRID_COLS.get(cards_per_page, 3)
    rows = math.ceil(cards_per_page / cols)

    # Split cards into page-sized chunks; pad the last page with None so the grid stays aligned
    raw_pages = [cards[i: i + cards_per_page] for i in range(0, len(cards), cards_per_page)]
    pages = []
    total_slots = cols * rows
    for chunk in raw_pages:
        padding = total_slots - len(chunk)
        pages.append({'cards': chunk, 'empty_range': range(padding)})

    return render(request, 'qr_generator/print.html', {
        'pages': pages,
        'cols': cols,
        'rows': rows,
        'cards_per_page': cards_per_page,
        'total_cards': len(cards),
    })


@admin_required
def teacher_qr_cards_config(request):
    """Step 1 – choose teachers and cards-per-page, then go to the print page."""
    if request.method == 'POST':
        teacher_ids = request.POST.getlist('teacher_ids')
        cards_per_page = request.POST.get('cards_per_page', '8')
        if not teacher_ids:
            messages.error(request, 'يرجى اختيار معلم واحد على الأقل.')
        else:
            request.session['qr_teacher_ids'] = teacher_ids
            request.session['qr_teacher_cards_per_page'] = cards_per_page
            from django.urls import reverse as _reverse
            return redirect(_reverse('qr_generator:teacher_qr_cards_print'))

    name_filter = request.GET.get('name', '').strip()
    subject_filter = request.GET.get('subject', '').strip()

    teachers = Teacher.objects.select_related('user').order_by('full_name')
    if name_filter:
        teachers = teachers.filter(full_name__icontains=name_filter)
    if subject_filter:
        teachers = teachers.filter(subject__icontains=subject_filter)

    subjects = (
        Teacher.objects.exclude(subject__isnull=True)
        .exclude(subject='')
        .values_list('subject', flat=True)
        .distinct()
        .order_by('subject')
    )

    return render(request, 'qr_generator/teacher_config.html', {
        'teachers': teachers,
        'subjects': subjects,
        'name_filter': name_filter,
        'subject_filter': subject_filter,
        'cards_per_page_range': range(1, 13),
    })


@admin_required
def teacher_qr_cards_print(request):
    """Step 2 – render a printable A4 page with teacher QR cards."""
    teacher_ids = request.session.pop('qr_teacher_ids', None) or request.GET.getlist('tid')
    try:
        cpp_raw = request.session.pop('qr_teacher_cards_per_page', None) or request.GET.get('cpp', 8)
        cards_per_page = max(1, min(12, int(cpp_raw)))
    except (ValueError, TypeError):
        cards_per_page = 8

    teachers = Teacher.objects.filter(id__in=teacher_ids).order_by('full_name')

    cards = [
        {'teacher': t, 'qr': _generate_qr_base64(str(t.id))}
        for t in teachers
    ]

    cols = CARDS_GRID_COLS.get(cards_per_page, 3)
    rows = math.ceil(cards_per_page / cols)

    raw_pages = [cards[i: i + cards_per_page] for i in range(0, len(cards), cards_per_page)]
    pages = []
    total_slots = cols * rows
    for chunk in raw_pages:
        padding = total_slots - len(chunk)
        pages.append({'cards': chunk, 'empty_range': range(padding)})

    return render(request, 'qr_generator/teacher_print.html', {
        'pages': pages,
        'cols': cols,
        'rows': rows,
        'cards_per_page': cards_per_page,
        'total_cards': len(cards),
    })
