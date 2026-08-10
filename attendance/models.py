"""Attendance models for student and teacher daily records."""

import uuid
from django.db import models

from core.models import Student, Teacher, User


class StudentAttendanceRecord(models.Model):
    """Daily attendance record for a student."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        help_text='Student who checked in',
    )
    date = models.DateField(db_index=True)
    check_in_time = models.DateTimeField()
    check_out_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Time the student left (set on second scan)',
    )
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_student_attendance',
        help_text='Admin user who recorded attendance',
    )
    original_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='original_student_attendance_records',
        help_text='Default/original teacher for the student',
    )
    assigned_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_student_attendance_records',
        help_text='Teacher assigned for this attendance day (substitute aware)',
    )
    substitute_note = models.CharField(
        max_length=255,
        blank=True,
        help_text='Reason/details when assigned teacher differs from original teacher',
    )
    daily_photo = models.ImageField(
        upload_to='attendance/daily_photos/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text='Optional daily photo captured for the student',
    )
    rating = models.PositiveSmallIntegerField(
        default=6,
        help_text='Daily student rating from 1 to 10',
    )
    teacher_note = models.TextField(
        blank=True,
        default='',
        help_text='Teacher note for this attendance record',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'student_attendance_records'
        verbose_name = 'Student Attendance Record'
        verbose_name_plural = 'Student Attendance Records'
        ordering = ['-date', '-check_in_time']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'date'],
                name='unique_student_attendance_per_day',
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1) & models.Q(rating__lte=10),
                name='student_attendance_rating_range_1_to_10',
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.date}"

    @property
    def is_substitute_assignment(self) -> bool:
        """True when student was attended by a substitute teacher for the day."""
        return (
            self.original_teacher_id is not None
            and self.assigned_teacher_id is not None
            and self.original_teacher_id != self.assigned_teacher_id
        )

    @property
    def is_checked_out(self) -> bool:
        """True when the student has a recorded check-out time."""
        return self.check_out_time is not None

    @property
    def duration(self):
        """Return timedelta of student's presence, or None if not checked out."""
        if self.check_in_time and self.check_out_time:
            return self.check_out_time - self.check_in_time
        return None

    @property
    def duration_display(self) -> str:
        """Human-readable duration string, e.g. '2س 30د'."""
        delta = self.duration
        if delta is None:
            return '—'
        total_minutes = int(delta.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        if hours and minutes:
            return f'{hours}س {minutes}د'
        if hours:
            return f'{hours}س'
        return f'{minutes}د'


class TeacherAttendanceRecord(models.Model):
    """Daily attendance record for a teacher."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    class RecordType(models.TextChoices):
        NORMAL = 'normal', 'حضور عادي'
        EXCUSED_ABSENCE = 'excused_absence', 'غياب بإذن'

    record_type = models.CharField(
        max_length=20,
        choices=RecordType.choices,
        default=RecordType.NORMAL,
        help_text='نوع السجل'
    )
    
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        help_text='Teacher who checked in',
    )
    date = models.DateField(db_index=True)
    check_in_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Time the teacher checked in (null if excused absence)'
    )
    check_out_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Time the teacher left (set on second scan)',
    )
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_teacher_attendance',
        help_text='Admin user who recorded attendance',
    )
    rating = models.PositiveSmallIntegerField(
        default=5,
        help_text='Daily teacher rating from 1 to 10',
    )
    notes = models.TextField(
        blank=True,
        default='',
        help_text='Admin notes for this attendance record',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'teacher_attendance_records'
        verbose_name = 'Teacher Attendance Record'
        verbose_name_plural = 'Teacher Attendance Records'
        ordering = ['-date', '-check_in_time']
        constraints = [
            models.UniqueConstraint(
                fields=['teacher', 'date'],
                name='unique_teacher_attendance_per_day',
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1) & models.Q(rating__lte=10),
                name='teacher_attendance_rating_range_1_to_10',
            ),
        ]

    def __str__(self) -> str:
        return f"{self.teacher.full_name} - {self.date}"

    @property
    def is_checked_out(self) -> bool:
        """True when the teacher has a recorded check-out time."""
        return self.check_out_time is not None

    @property
    def duration(self):
        """Return timedelta of teacher's presence, or None if not checked out."""
        if self.check_in_time and self.check_out_time:
            return self.check_out_time - self.check_in_time
        return None

    @property
    def duration_display(self) -> str:
        """Human-readable duration string, e.g. '2س 30د'."""
        delta = self.duration
        if delta is None:
            return '—'
        total_minutes = int(delta.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        if hours and minutes:
            return f'{hours}س {minutes}د'
        if hours:
            return f'{hours}س'
        return f'{minutes}د'

    def __str__(self) -> str:
        return f"{self.teacher.full_name} - {self.date}"
