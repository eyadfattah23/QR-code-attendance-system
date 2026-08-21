from decimal import Decimal

from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

from core.models import CoursePayment, Student, StudentTeacherLink, Teacher, User


class CoursePaymentModelTests(TestCase):
    """Tests for the CoursePayment model constraints and behaviour."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            phone='01000000001', password='testpass123',
            role=User.Role.TEACHER,
        )
        cls.course_teacher = Teacher.objects.create(
            user=cls.user,
            full_name='دورة تجويد',
            is_course=True,
        )
        cls.student = Student.objects.create(
            full_name='طالب اختبار الدفع',
            student_code='PAY-001',
        )
        StudentTeacherLink.objects.create(
            student=cls.student, teacher=cls.course_teacher, is_primary=True,
        )

    def test_create_payment(self):
        """A payment record can be created with all required fields."""
        payment = CoursePayment.objects.create(
            student=self.student,
            course=self.course_teacher,
            year=2026, month=8,
            status=CoursePayment.PaymentStatus.PAID,
            amount_paid=Decimal('150.00'),
        )
        self.assertEqual(payment.get_status_display(), 'تم الدفع')

    def test_unique_together_prevents_duplicates(self):
        """Cannot create two payments for same (student, course, year, month)."""
        CoursePayment.objects.create(
            student=self.student,
            course=self.course_teacher,
            year=2026, month=8,
        )
        with self.assertRaises(IntegrityError):
            CoursePayment.objects.create(
                student=self.student,
                course=self.course_teacher,
                year=2026, month=8,
            )

    def test_different_month_allowed(self):
        """Same student+course but different month is allowed."""
        CoursePayment.objects.create(
            student=self.student, course=self.course_teacher,
            year=2026, month=7,
        )
        CoursePayment.objects.create(
            student=self.student, course=self.course_teacher,
            year=2026, month=8,
        )
        self.assertEqual(
            CoursePayment.objects.filter(student=self.student).count(), 2)

    def test_protect_on_delete_course(self):
        """Deleting a course-teacher with payments raises ProtectedError."""
        CoursePayment.objects.create(
            student=self.student, course=self.course_teacher,
            year=2026, month=8,
        )
        with self.assertRaises(ProtectedError):
            self.course_teacher.delete()

    def test_cascade_on_delete_student(self):
        """Deleting a student cascades to their payment records."""
        CoursePayment.objects.create(
            student=self.student, course=self.course_teacher,
            year=2026, month=8,
        )
        student_pk = self.student.pk
        self.student.delete()
        self.assertFalse(
            CoursePayment.objects.filter(student_id=student_pk).exists())

    def test_amount_paid_nullable(self):
        """amount_paid can be left null."""
        payment = CoursePayment.objects.create(
            student=self.student, course=self.course_teacher,
            year=2026, month=8,
        )
        self.assertIsNone(payment.amount_paid)

    def test_default_status_is_not_paid(self):
        """Default payment status is NOT_PAID."""
        payment = CoursePayment.objects.create(
            student=self.student, course=self.course_teacher,
            year=2026, month=8,
        )
        self.assertEqual(payment.status, CoursePayment.PaymentStatus.NOT_PAID)


class TeacherIsActiveDefaultTests(TestCase):
    """Tests for the Teacher.is_active and Teacher.description defaults."""

    def test_new_teacher_is_active_by_default(self):
        user = User.objects.create_user(
            phone='01000000099', password='testpass123',
            role=User.Role.TEACHER,
        )
        teacher = Teacher.objects.create(user=user, full_name='معلم جديد')
        self.assertTrue(teacher.is_active)

    def test_new_teacher_description_blank_by_default(self):
        user = User.objects.create_user(
            phone='01000000098', password='testpass123',
            role=User.Role.TEACHER,
        )
        teacher = Teacher.objects.create(user=user, full_name='معلم جديد 2')
        self.assertEqual(teacher.description, '')
