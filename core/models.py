"""
Core models for the QR Attendance System.

This module contains the base models used across the application:
- User: Custom user model with role-based access (admin, teacher)
- Student: Student records
- Teacher: Teacher profile linked to User
- StudentTeacherLink: Many-to-many relationship between students and teachers
"""

import re
import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


# Phone number validator: 11 digits starting with 0
phone_validator = RegexValidator(
    regex=r'^0\d{10}$',
    message='رقم الهاتف يجب أن يكون 11 رقم ويبدأ بصفر (مثال: 01234567890)'
)


def validate_phone_number(value: str) -> None:
    """Validate phone number format: 11 digits starting with 0."""
    if not re.match(r'^0\d{10}$', value):
        raise ValidationError(
            'رقم الهاتف يجب أن يكون 11 رقم ويبدأ بصفر (مثال: 01234567890)',
            code='invalid_phone'
        )


class UserManager(BaseUserManager):
    """Custom user manager that uses phone number for authentication."""

    def create_user(self, phone, password=None, **extra_fields):
        """Create and return a regular user with phone and password."""
        if not phone:
            raise ValueError('رقم الهاتف مطلوب')
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        """Create and return a superuser with phone and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model with role-based access control.

    Authentication is done via phone number instead of username.

    Roles:
        - admin: Full system access (manage students, teachers, view all records)
        - teacher: View own students, upload photos
    """

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        TEACHER = 'teacher', 'Teacher'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.TEACHER,
        help_text="User role determining access level"
    )
    phone = models.CharField(
        max_length=11,
        unique=True,
        validators=[phone_validator],
        help_text="رقم الهاتف: 11 رقم يبدأ بصفر (مثال: 01234567890)"
    )

    # Make username not required (we use phone for login)
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        null=True,
        help_text="Optional username (phone is used for login)"
    )

    # Use phone as the username field for authentication
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['email']  # Required when creating superuser

    # Custom manager for phone-based authentication
    objects = UserManager()

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.phone} ({self.role})"

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == self.Role.ADMIN

    @property
    def is_teacher(self) -> bool:
        """Check if user has teacher role."""
        return self.role == self.Role.TEACHER


class Student(models.Model):
    """
    Student model representing a student in the system.

    Students are identified by a UUID which is encoded in their QR code.
    They can be linked to multiple teachers (different subjects).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier used in QR code"
    )
    national_id = models.CharField(
        max_length=50,
        unique=True,
        help_text="National ID or student registration number"
    )
    student_code = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        help_text="Easy student ID for manual entry (e.g., STU1001)"
    )
    full_name = models.CharField(
        max_length=255,
        help_text="Student's full name"
    )
    grade = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Grade or class (e.g., 'Grade 5', 'Year 2')"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'students'
        ordering = ['full_name']
        verbose_name = 'Student'
        verbose_name_plural = 'Students'

    def __str__(self) -> str:
        label = self.student_code or self.national_id
        return f"{self.full_name} ({label})"

    def save(self, *args, **kwargs):
        """Auto-fill student_code from national_id when not provided."""
        if not self.student_code and self.national_id:
            self.student_code = self.national_id.strip().upper()
        super().save(*args, **kwargs)


class Teacher(models.Model):
    """
    Teacher profile model linked to a User account.

    Teachers are also identified by a UUID for QR code scanning.
    They have a user account for portal access.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier used in QR code"
    )
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='teacher_profile',
        help_text="Linked user account for portal access"
    )
    full_name = models.CharField(
        max_length=255,
        help_text="Teacher's full name"
    )
    subject = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Primary subject taught"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'teachers'
        ordering = ['full_name']
        verbose_name = 'Teacher'
        verbose_name_plural = 'Teachers'

    def __str__(self) -> str:
        return f"{self.full_name}"


class StudentTeacherLink(models.Model):
    """
    Many-to-many relationship between students and teachers.

    A student can be linked to multiple teachers (different subjects).
    A teacher can have multiple students assigned to them.
    """

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='teacher_links',
        help_text="The student in this relationship"
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name='student_links',
        help_text="The teacher in this relationship"
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the student's primary teacher"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'student_teacher_links'
        unique_together = ['student', 'teacher']
        verbose_name = 'Student-Teacher Link'
        verbose_name_plural = 'Student-Teacher Links'

    def __str__(self) -> str:
        primary = " (Primary)" if self.is_primary else ""
        return f"{self.student.full_name} → {self.teacher.full_name}{primary}"
