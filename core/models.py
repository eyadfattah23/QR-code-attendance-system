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
        SUPERVISOR = 'supervisor', 'Supervisor'

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

    @property
    def is_supervisor(self) -> bool:
        """Check if user has supervisor role."""
        return self.role == self.Role.SUPERVISOR


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
        unique=True,
        help_text="Student's full name"
    )
    nickname = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Nickname or short name (اللقب / الاسم المختصر)",
    )
    grade = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Grade or class (e.g., 'Grade 5', 'Year 2')"
    )

    class Gender(models.TextChoices):
        MALE = 'M', 'ذكر'
        FEMALE = 'F', 'أنثى'

    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        blank=True,
        null=True,
        help_text="Student gender",
    )
    
    image = models.ImageField(
        upload_to='students/images/%Y/%m/',
        null=True,
        blank=True,
        help_text="صورة الطالب",
    )

    _egyptian_phone_validator = RegexValidator(
        regex=r'^01\d{9}$',
        message="رقم الهاتف يجب أن يتكون من 11 رقماً ويبدأ بـ 01",
    )

    phone = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        validators=[_egyptian_phone_validator],
        help_text="Student phone number (11 digits starting with 01)",
    )
    parent_phone = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        validators=[_egyptian_phone_validator],
        help_text="Parent WhatsApp number (11 digits starting with 01)",
    )
    # --------------- Parent / Guardian information ---------------
    parent_full_name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="الاسم الرباعي لولي الأمر",
    )
    parent_qualification = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="المؤهل الدراسي لولي الأمر",
    )
    parent_job = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="الوظيفة الحالية لولي الأمر",
    )
    parent_calls_phone = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        validators=[_egyptian_phone_validator],
        help_text="رقم هاتف المكالمات لولي الأمر (11 رقماً يبدأ بـ 01)",
    )

    class MaritalStatus(models.TextChoices):
        MARRIED = 'married', 'متزوج'
        DIVORCED = 'divorced', 'مطلق'
        WIDOWED = 'widowed', 'أرمل'
        SEPARATED = 'separated', 'منفصل'

    parent_marital_status = models.CharField(
        max_length=20,
        choices=MaritalStatus.choices,
        blank=True,
        default='',
        help_text="الحالة الاجتماعية لولي الأمر",
    )
    parent_spouse_job = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="وظيفة الزوج / الزوجة (إن وُجدت)",
    )
    parent_address = models.TextField(
        blank=True,
        default='',
        help_text="عنوان السكن",
    )
    child_pickup_person = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="من يستلم الطفل بعد الانتهاء",
    )
    # --------------- Dates & extra ---------------
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        help_text="تاريخ الميلاد",
    )
    joining_date = models.DateField(
        blank=True,
        null=True,
        help_text="تاريخ الانضمام (يُدخله المشرف)",
    )
    hall_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="اسم القاعة / المجموعة",
    )
    notes = models.TextField(
        blank=True,
        default='',
        help_text="ملاحظات إضافية",
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
        
        if self.image:
            try:
                import os
                from PIL import Image
                img_path = self.image.path
                if os.path.exists(img_path):
                    # Check file size or just compress
                    img = Image.open(img_path)
                    
                    changed = False
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                        changed = True
                    
                    max_size = (500, 500)
                    if img.width > max_size[0] or img.height > max_size[1]:
                        img.thumbnail(max_size, Image.Resampling.LANCZOS)
                        changed = True
                        
                    # Even if not resized, we can re-save with lower quality to compress
                    # To avoid re-compressing every save, we check if it was just uploaded or something.
                    # But overwriting it once is fine.
                    img.save(img_path, format='JPEG', quality=60, optimize=True)
            except Exception as e:
                pass

    @property
    def age(self):
        """Return current age in years, or None if date_of_birth is not set."""
        if not self.date_of_birth:
            return None
        from datetime import date
        today = date.today()
        return (
            today.year - self.date_of_birth.year
            - ((today.month, today.day) <
               (self.date_of_birth.month, self.date_of_birth.day))
        )


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

    class Gender(models.TextChoices):
        MALE = 'M', 'ذكر'
        FEMALE = 'F', 'أنثى'

    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        blank=True,
        null=True,
        help_text="Teacher gender",
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
