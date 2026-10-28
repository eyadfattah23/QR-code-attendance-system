"""Attendance rules shared by the QR scan station and the fingerprint device."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.utils.timezone import localtime

from .models import TeacherAttendanceRecord, TeacherScanOutcome

# A second scan sooner than this after check-in is an accidental repeat, not a check-out.
MIN_CHECKOUT_DELAY = timedelta(minutes=5)


@dataclass
class TeacherScan:
    """Result of one teacher scan: what happened, the day's record, and the scan time."""

    outcome: TeacherScanOutcome
    record: TeacherAttendanceRecord
    at: datetime


def record_teacher_scan(teacher, at=None, recorded_by=None) -> TeacherScan:
    """Apply one teacher scan: the day's first scan checks in, the next one checks out.

    ``at`` is the scan time (defaults to now). The fingerprint device passes the
    punch time so that punches it uploads late still land on the right day.
    """
    at = localtime(at)
    day = at.date()

    with transaction.atomic():
        record = (
            TeacherAttendanceRecord.objects.select_for_update()
            .filter(teacher=teacher, date=day)
            .first()
        )
        if record is None:
            try:
                with transaction.atomic():
                    record = TeacherAttendanceRecord.objects.create(
                        teacher=teacher,
                        date=day,
                        check_in_time=at,
                        recorded_by=recorded_by,
                    )
                return TeacherScan(TeacherScanOutcome.CHECKED_IN, record, at)
            except IntegrityError:
                # Another scan for the same day was saved first; treat this one as its follow-up.
                record = TeacherAttendanceRecord.objects.select_for_update().get(
                    teacher=teacher, date=day)

        if record.record_type == TeacherAttendanceRecord.RecordType.EXCUSED_ABSENCE:
            outcome = TeacherScanOutcome.EXCUSED_ABSENCE
        elif record.check_out_time is not None:
            outcome = TeacherScanOutcome.ALREADY_CHECKED_OUT
        elif at < record.check_in_time:
            outcome = TeacherScanOutcome.BEFORE_CHECK_IN
        elif at - record.check_in_time < MIN_CHECKOUT_DELAY:
            outcome = TeacherScanOutcome.TOO_EARLY
        else:
            record.check_out_time = at
            record.save(update_fields=['check_out_time'])
            outcome = TeacherScanOutcome.CHECKED_OUT

    return TeacherScan(outcome, record, at)
