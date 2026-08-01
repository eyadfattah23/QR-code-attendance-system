from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import redirect, render, get_object_or_404
from django.utils.timezone import localdate
from django.views.decorators.http import require_http_methods
from functools import wraps

from core.models import Teacher, StudentTeacherLink
from attendance.models import StudentAttendanceRecord


def supervisor_required(view_func):
    """Decorator to ensure the user has the supervisor role."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_supervisor:
            messages.error(request, 'ليس لديك صلاحية الوصول لهذه الصفحة')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@supervisor_required
def dashboard(request):
    """Supervisor dashboard — list of all teachers as cards."""
    today = localdate()
    
    subject = request.GET.get('subject', '').strip()
    sort_by = request.GET.get('sort', '').strip()

    teachers = (
        Teacher.objects
        .select_related('user')
        .annotate(
            student_count=Count('student_links', distinct=True),
            today_count=Count(
                'assigned_student_attendance_records',
                filter=Q(assigned_student_attendance_records__date=today),
                distinct=True
            )
        )
    )

    if subject:
        teachers = teachers.filter(subject=subject)

    if sort_by == 'students_desc':
        teachers = teachers.order_by('-student_count', 'full_name')
    elif sort_by == 'students_asc':
        teachers = teachers.order_by('student_count', 'full_name')
    elif sort_by == 'attended_asc':
        teachers = teachers.order_by('today_count', 'full_name')
    elif sort_by == 'name':
        teachers = teachers.order_by('full_name')
    else:
        # Default sort
        sort_by = 'attended_desc'
        teachers = teachers.order_by('-today_count', 'full_name')

    teacher_cards = []
    for t in teachers:
        teacher_cards.append({
            'teacher': t,
            'student_count': t.student_count,
            'today_count': t.today_count,
            'is_active': str(t.pk) == request.session.get('supervisor_teacher_id', ''),
        })
        
    subjects = Teacher.objects.exclude(subject__isnull=True).exclude(subject='').values_list('subject', flat=True).distinct().order_by('subject')

    return render(request, 'supervisor_portal/dashboard.html', {
        'teacher_cards': teacher_cards,
        'today': today,
        'active_teacher_id': request.session.get('supervisor_teacher_id', ''),
        'subject_q': subject,
        'sort_by': sort_by,
        'subjects': subjects,
    })


@supervisor_required
@require_http_methods(['POST'])
def select_teacher(request, pk):
    """Store the chosen teacher in session and redirect to teacher portal."""
    teacher = get_object_or_404(Teacher, pk=pk)
    request.session['supervisor_teacher_id'] = str(teacher.pk)
    messages.success(
        request, f'أنت الآن تعمل بصلاحيات المعلم: {teacher.full_name}')
    return redirect('teacher_portal:dashboard')


@supervisor_required
@require_http_methods(['POST'])
def deselect_teacher(request):
    """Clear the selected teacher from session and return to supervisor dashboard."""
    request.session.pop('supervisor_teacher_id', None)
    return redirect('supervisor_portal:dashboard')
