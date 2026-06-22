import uuid
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.timezone import localdate, localtime
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect

from core.models import Student, StudentTeacherLink, Teacher

from .models import StudentAttendanceRecord, TeacherAttendanceRecord


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

    if request.method == "POST":
        scanned_codes = request.POST.get("scanned_codes", "").strip()
        codes = [line.strip()
                 for line in scanned_codes.splitlines() if line.strip()]

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
                        results.append(
                            {
                                "status": "success",
                                "icon": "bi-check-circle-fill",
                                        "label": "تم التسجيل",
                                        "message": f"{student.full_name} - تم تسجيل الحضور بنجاح",
                                        "row_class": "success",
                            }
                        )
                    else:
                        results.append(
                            {
                                "status": "warning",
                                "icon": "bi-exclamation-circle-fill",
                                        "label": "مسجل مسبقاً",
                                        "message": (
                                            f"{student.full_name} - مسجل مسبقاً الساعة "
                                            f"{student_record.check_in_time.strftime('%H:%M')}"
                                        ),
                                "row_class": "warning",
                            }
                        )
                    continue

                if teacher is not None:
                    from django.db import transaction as _tx
                    with _tx.atomic():
                        try:
                            teacher_record = TeacherAttendanceRecord.objects.select_for_update().get(
                                teacher=teacher,
                                date=today,
                            )
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
                    "time": record.check_in_time,
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
        recent_scans, key=lambda item: item["time"], reverse=True)[:10]

    context = {
        "scanned_codes": scanned_codes,
        "results": results,
        "success_count": success_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "total_count": len(results),
        "recent_scans": recent_scans,
        "total_today": total_today,
    }
    return render(request, "scan/station.html", context)
