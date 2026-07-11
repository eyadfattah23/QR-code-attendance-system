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

    teachers = (
        Teacher.objects
        .select_related('user')
        .annotate(student_count=Count('student_links', distinct=True))
        .order_by('full_name')
    )

    # Build today's attendance counts per teacher
    today_records = (
        StudentAttendanceRecord.objects
        .filter(date=today)
        .values('assigned_teacher_id')
        .annotate(count=Count('id'))
    )
    today_count_by_teacher = {
        r['assigned_teacher_id']: r['count'] for r in today_records}

    teacher_cards = []
    for t in teachers:
        teacher_cards.append({
            'teacher': t,
            'student_count': t.student_count,
            'today_count': today_count_by_teacher.get(t.id, 0),
            'is_active': str(t.pk) == request.session.get('supervisor_teacher_id', ''),
        })

    return render(request, 'supervisor_portal/dashboard.html', {
        'teacher_cards': teacher_cards,
        'today': today,
        'active_teacher_id': request.session.get('supervisor_teacher_id', ''),
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
