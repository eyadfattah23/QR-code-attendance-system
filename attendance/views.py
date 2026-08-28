import uuid
from datetime import datetime, timezone
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction as _tx
from django.utils.timezone import localdate, localtime
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect

from core.models import Student, StudentTeacherLink, Teacher

from .models import StudentAttendanceRecord, TeacherAttendanceRecord


def _checkout_student_record(results, student, record):
    """Attempt to check out an open StudentAttendanceRecord.

    Appends the appropriate result dict (warning on time-skew/too-early,
    otherwise performs the checkout and appends a success result).
    """
    now = localtime()
    if now < record.check_in_time:
        results.append({
            "status": "warning",
            "icon": "bi-exclamation-circle-fill",
            "label": "خطأ في التوقيت",
            "message": (
                f"{student.full_name} - وقت المغادرة "
                f"({now.strftime('%H:%M')}) قبل وقت الحضور "
                f"({record.check_in_time.strftime('%H:%M')})"
            ),
            "row_class": "warning",
            "image_url": student.image.url if student.image else None,
        })
        return
    if (now - record.check_in_time).total_seconds() < 300:
        elapsed = int((now - record.check_in_time).total_seconds() // 60)
        remaining = 5 - elapsed
        results.append({
            "status": "warning",
            "icon": "bi-clock-fill",
            "label": "مبكر جداً",
            "message": (
                f"{student.full_name} - لا يمكن تسجيل المغادرة "
                f"قبل مرور 5 دقائق من الحضور "
                f"(باقي {remaining} دقيقة)"
            ),
            "row_class": "warning",
            "image_url": student.image.url if student.image else None,
        })
        return
    record.check_out_time = now
    record.save(update_fields=['check_out_time'])
    course_suffix = (
        f" (حصة: {record.original_teacher.full_name})"
        if record.original_teacher_id else ""
    )
    results.append({
        "status": "checkout",
        "icon": "bi-door-open-fill",
        "label": "تم تسجيل المغادرة",
        "message": (
            f"{student.full_name} - غادر الساعة "
            f"{now.strftime('%H:%M')}{course_suffix} | "
            f"مدة الحضور: {record.duration_display}"
        ),
        "row_class": "info",
        "image_url": student.image.url if student.image else None,
    })


def admin_required(view_func):
    """Decorator to ensure user is an admin."""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin:
            messages.error(request, 'ليس لديك صلاحية الوصول إلى محطة المسح')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@admin_required
@require_http_methods(["GET", "POST"])
def station_view(request):
    """Render scan station and process a submitted batch of scanned codes."""
    results = []
    scanned_codes = ""
    session_teacher_id = ""
    allow_unenrolled = False

    if request.method == "POST":
        scanned_codes = request.POST.get("scanned_codes", "").strip()
        session_teacher_id = request.POST.get("session_teacher", "").strip()
        allow_unenrolled = request.POST.get("allow_unenrolled") == "on"
        codes = [line.strip()
                 for line in scanned_codes.splitlines() if line.strip()]

        # Resolve session_teacher (the course dropdown)
        session_teacher = None
        if session_teacher_id:
            try:
                session_teacher = Teacher.objects.get(pk=session_teacher_id)
            except (Teacher.DoesNotExist, ValueError):
                session_teacher = None

        if not codes:
            messages.warning(
                request, "الرجاء إدخال رمز واحد على الأقل قبل الإرسال")
        else:
            today = localdate()

            for raw_code in codes:
                student = None
                teacher = None

                try:
                    code_uuid = uuid.UUID(raw_code)
                    student = Student.objects.filter(id=code_uuid).first()
                    if student is None:
                        teacher = Teacher.objects.filter(id=code_uuid).first()
                except ValueError:
                    # Allow manual entry by easy student code or national ID.
                    lookup = raw_code.strip().upper()
                    student = Student.objects.filter(
                        student_code__iexact=lookup).first()
                    if student is None:
                        student = Student.objects.filter(
                            national_id__iexact=lookup).first()
                    if student is None:
                        teacher = Teacher.objects.filter(
                            teacher_code__iexact=lookup).first()

                if student is not None:
                    with _tx.atomic():
                        open_records = list(
                            StudentAttendanceRecord.objects.select_for_update(of=("self",))
                            .filter(student=student, date=today,
                                    check_out_time__isnull=True)
                            .select_related("original_teacher")
                        )

                        if session_teacher is None:
                            # Automatic mode — decide based on open sessions today.
                            if len(open_records) == 0:
                                primary_link = (
                                    StudentTeacherLink.objects.filter(
                                        student=student)
                                    .order_by("-is_primary", "created_at")
                                    .select_related("teacher")
                                    .first()
                                )
                                record_teacher = primary_link.teacher if primary_link else None

                                closed_today = StudentAttendanceRecord.objects.filter(
                                    student=student, date=today,
                                    original_teacher=record_teacher,
                                    check_out_time__isnull=False,
                                ).first()

                                if closed_today is not None:
                                    results.append({
                                        "status": "warning",
                                        "icon": "bi-exclamation-circle-fill",
                                        "label": "مغادرة مسجلة مسبقاً",
                                        "message": (
                                            f"{student.full_name} - غادر مسبقاً الساعة "
                                            f"{closed_today.check_out_time.strftime('%H:%M')}"
                                        ),
                                        "row_class": "warning",
                                        "image_url": student.image.url if student.image else None,
                                    })
                                else:
                                    try:
                                        StudentAttendanceRecord.objects.create(
                                            student=student,
                                            date=today,
                                            check_in_time=localtime(),
                                            recorded_by=request.user,
                                            original_teacher=record_teacher,
                                            assigned_teacher=record_teacher,
                                            substitute_note="",
                                            rating=6,
                                        )
                                        course_suffix = (
                                            f" (حصة: {record_teacher.full_name})"
                                            if record_teacher else ""
                                        )
                                        results.append({
                                            "status": "success",
                                            "icon": "bi-check-circle-fill",
                                            "label": "تم التسجيل",
                                            "message": f"{student.full_name} - تم تسجيل الحضور بنجاح{course_suffix}",
                                            "row_class": "success",
                                            "image_url": student.image.url if student.image else None,
                                        })
                                    except IntegrityError:
                                        results.append({
                                            "status": "warning",
                                            "icon": "bi-exclamation-circle-fill",
                                            "label": "تم التسجيل من جهاز آخر",
                                            "message": f"{student.full_name} - تم تسجيل حضوره للتو من محطة أخرى",
                                            "row_class": "warning",
                                            "image_url": student.image.url if student.image else None,
                                        })
                            elif len(open_records) == 1:
                                _checkout_student_record(
                                    results, student, open_records[0])
                            else:
                                course_names = ", ".join(
                                    r.original_teacher.full_name if r.original_teacher else "بدون حصة"
                                    for r in open_records
                                )
                                results.append({
                                    "status": "warning",
                                    "icon": "bi-exclamation-triangle-fill",
                                    "label": "أكثر من حصة مفتوحة",
                                    "message": (
                                        f"{student.full_name} - لديه أكثر من حصة مفتوحة اليوم "
                                        f"({course_names}) — يرجى اختيار الحصة من القائمة"
                                    ),
                                    "row_class": "warning border border-warning border-2",
                                    "action": "ambiguous",
                                    "image_url": student.image.url if student.image else None,
                                })
                        else:
                            # Explicit course selected from the dropdown.
                            matching = next(
                                (r for r in open_records
                                 if r.original_teacher_id == session_teacher.id),
                                None,
                            )
                            if matching is not None:
                                _checkout_student_record(
                                    results, student, matching)
                            else:
                                closed_today = StudentAttendanceRecord.objects.filter(
                                    student=student, date=today,
                                    original_teacher=session_teacher,
                                    check_out_time__isnull=False,
                                ).first()
                                if closed_today is not None:
                                    results.append({
                                        "status": "warning",
                                        "icon": "bi-exclamation-circle-fill",
                                        "label": "مغادرة مسجلة مسبقاً",
                                        "message": (
                                            f"{student.full_name} - غادر مسبقاً حصة "
                                            f"{session_teacher.full_name} الساعة "
                                            f"{closed_today.check_out_time.strftime('%H:%M')}"
                                        ),
                                        "row_class": "warning",
                                        "image_url": student.image.url if student.image else None,
                                    })
                                else:
                                    is_enrolled = StudentTeacherLink.objects.filter(
                                        student=student, teacher=session_teacher
                                    ).exists()
                                    if not is_enrolled and not allow_unenrolled:
                                        results.append({
                                            "status": "error",
                                            "icon": "bi-exclamation-octagon-fill",
                                            "label": "غير مسجل في هذه الحصة",
                                            "message": (
                                                f"{student.full_name} - غير مسجل في حصة "
                                                f"{session_teacher.full_name}."
                                            ),
                                            "row_class": "danger border border-danger border-2",
                                            "action": "force_enroll",
                                            "action_code": raw_code,
                                            "image_url": student.image.url if student.image else None,
                                        })
                                    else:
                                        try:
                                            StudentAttendanceRecord.objects.create(
                                                student=student,
                                                date=today,
                                                check_in_time=localtime(),
                                                recorded_by=request.user,
                                                original_teacher=session_teacher,
                                                assigned_teacher=session_teacher,
                                                substitute_note="",
                                                rating=6,
                                            )
                                            results.append({
                                                "status": "success",
                                                "icon": "bi-check-circle-fill",
                                                "label": "تم التسجيل",
                                                "message": (
                                                    f"{student.full_name} - تم تسجيل الحضور بنجاح "
                                                    f"(حصة: {session_teacher.full_name})"
                                                ),
                                                "row_class": "success",
                                                "image_url": student.image.url if student.image else None,
                                            })
                                        except IntegrityError:
                                            results.append({
                                                "status": "warning",
                                                "icon": "bi-exclamation-circle-fill",
                                                "label": "تم التسجيل من جهاز آخر",
                                                "message": (
                                                    f"{student.full_name} - تم تسجيل حضور حصة "
                                                    f"{session_teacher.full_name} للتو من محطة أخرى"
                                                ),
                                                "row_class": "warning",
                                                "image_url": student.image.url if student.image else None,
                                            })
                    continue

                if teacher is not None:
                    with _tx.atomic():
                        try:
                            teacher_record = TeacherAttendanceRecord.objects.select_for_update().get(
                                teacher=teacher,
                                date=today,
                            )

                            if teacher_record.record_type == TeacherAttendanceRecord.RecordType.EXCUSED_ABSENCE:
                                results.append({
                                    "status": "warning",
                                    "icon": "bi-exclamation-circle-fill",
                                    "label": "غياب مسجل مسبقاً",
                                    "message": f"{teacher.full_name} (معلم) - مسجل غياب بإذن لهذا اليوم.",
                                    "row_class": "warning",
                                })
                                continue

                            # Record exists — second scan = check-out
                            if teacher_record.check_out_time is not None:
                                # Already checked out
                                results.append({
                                    "status": "warning",
                                    "icon": "bi-exclamation-circle-fill",
                                    "label": "مغادرة مسجلة مسبقاً",
                                    "message": (
                                        f"{teacher.full_name} (معلم) - غادر مسبقاً الساعة "
                                        f"{teacher_record.check_out_time.strftime('%H:%M')}"
                                    ),
                                    "row_class": "warning",
                                })
                            else:
                                # First checkout scan
                                now = localtime()
                                if now < teacher_record.check_in_time:
                                    # Clock skew — reject
                                    results.append({
                                        "status": "warning",
                                        "icon": "bi-exclamation-circle-fill",
                                        "label": "خطأ في التوقيت",
                                        "message": (
                                            f"{teacher.full_name} (معلم) - وقت المغادرة "
                                            f"({now.strftime('%H:%M')}) قبل وقت الحضور "
                                            f"({teacher_record.check_in_time.strftime('%H:%M')})"
                                        ),
                                        "row_class": "warning",
                                    })
                                elif (now - teacher_record.check_in_time).total_seconds() < 300:
                                    # Less than 5 minutes since check-in — reject
                                    elapsed = int(
                                        (now - teacher_record.check_in_time).total_seconds() // 60)
                                    remaining = 5 - elapsed
                                    results.append({
                                        "status": "warning",
                                        "icon": "bi-clock-fill",
                                        "label": "مبكر جداً",
                                        "message": (
                                            f"{teacher.full_name} (معلم) - لا يمكن تسجيل المغادرة "
                                            f"قبل مرور 5 دقائق من الحضور "
                                            f"(باقي {remaining} دقيقة)"
                                        ),
                                        "row_class": "warning",
                                    })
                                else:
                                    teacher_record.check_out_time = now
                                    teacher_record.save(
                                        update_fields=['check_out_time'])
                                    results.append({
                                        "status": "checkout",
                                        "icon": "bi-door-open-fill",
                                        "label": "تم تسجيل المغادرة",
                                        "message": (
                                            f"{teacher.full_name} (معلم) - غادر الساعة "
                                            f"{now.strftime('%H:%M')} | "
                                            f"مدة الحضور: {teacher_record.duration_display}"
                                        ),
                                        "row_class": "info",
                                    })
                        except TeacherAttendanceRecord.DoesNotExist:
                            # No record today — first scan = check-in
                            TeacherAttendanceRecord.objects.create(
                                teacher=teacher,
                                date=today,
                                check_in_time=localtime(),
                                recorded_by=request.user,
                            )
                            results.append({
                                "status": "success",
                                "icon": "bi-check-circle-fill",
                                "label": "تم التسجيل",
                                "message": f"{teacher.full_name} (معلم) - تم تسجيل الحضور بنجاح",
                                "row_class": "success",
                            })
                    continue

                results.append(
                    {
                        "status": "error",
                        "icon": "bi-x-circle-fill",
                                "label": "غير موجود",
                                "message": (
                                    f"لم يتم العثور على سجل مطابق للرمز: {raw_code} "
                                    "(UUID أو student_code أو national_id)"
                                ),
                        "row_class": "danger",
                    }
                )

    success_count = sum(
        1 for item in results if item["status"] in ("success", "checkout"))
    warning_count = sum(1 for item in results if item["status"] == "warning")
    error_count = sum(1 for item in results if item["status"] == "error")

    today = localdate()
    total_today = (
        StudentAttendanceRecord.objects.filter(date=today).count()
        + TeacherAttendanceRecord.objects.filter(date=today).count()
    )
    recent_student_scans = (
        StudentAttendanceRecord.objects.filter(date=today)
        .select_related("student")
        .order_by("-check_in_time")[:8]
    )
    recent_teacher_scans = (
        TeacherAttendanceRecord.objects.filter(date=today)
        .select_related("teacher")
        .order_by("-check_in_time")[:8]
    )

    recent_scans = [
        {
            "kind": "student",
            "name": record.student.full_name,
            "code": record.student.student_code or record.student.national_id,
            "time": record.check_out_time if record.check_out_time else record.check_in_time,
            "is_checkout": record.check_out_time is not None,
        }
        for record in recent_student_scans
    ] + [
        {
            "kind": "teacher",
            "name": record.teacher.full_name,
            "code": "Teacher",
            "time": record.check_out_time if record.check_out_time else record.check_in_time,
            "is_checkout": record.check_out_time is not None,
        }
        for record in recent_teacher_scans
    ]
    recent_scans = sorted(
        recent_scans,
        key=lambda item: item["time"] if item["time"] is not None else datetime.min.replace(
            tzinfo=timezone.utc),
        reverse=True,
    )[:10]
    courses = Teacher.objects.filter(
        is_course=True, is_active=True).order_by('full_name')

    context = {
        "scanned_codes": scanned_codes,
        "results": results,
        "success_count": success_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "total_count": len(results),
        "recent_scans": recent_scans,
        "total_today": total_today,
        "courses": courses,
        "session_teacher_id": session_teacher_id,
        "allow_unenrolled": allow_unenrolled,
    }
    return render(request, "scan/station.html", context)
