"""
Tests for multi-course attendance constraints and scan station behavior.

Covers:
- Database constraint enforcement (per-course unique, no-course guard)
- Station scan with session_teacher (course dropdown)
- Station scan in automatic mode (primary link teacher)
- Checkout logic with/without course selection
"""

import uuid
from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils.timezone import localdate, localtime

from core.models import User, Student, Teacher, StudentTeacherLink
from attendance.models import StudentAttendanceRecord


class MultiCourseConstraintTestCase(TestCase):
    """Test that the new DB constraints enforce correct uniqueness."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_user(
            phone='01000000001',
            email='admin-c@test.com',
            password='pass123',
            role=User.Role.ADMIN,
        )
        cls.teacher_a = Teacher.objects.create(
            user=User.objects.create_user(
                phone='01000000002', email='ta@test.com',
                password='pass123', role=User.Role.TEACHER,
            ),
            full_name='Teacher A',
            is_course=True,
        )
        cls.teacher_b = Teacher.objects.create(
            user=User.objects.create_user(
                phone='01000000003', email='tb@test.com',
                password='pass123', role=User.Role.TEACHER,
            ),
            full_name='Teacher B',
            is_course=True,
        )
        cls.student = Student.objects.create(
            national_id='NID_CONST_01',
            full_name='Student Constraint Test',
        )

    def test_single_course_per_day(self):
        """A student can have one attendance row per course per day."""
        rec = StudentAttendanceRecord.objects.create(
            student=self.student,
            date=localdate(),
            check_in_time=localtime(),
            original_teacher=self.teacher_a,
            assigned_teacher=self.teacher_a,
        )
        self.assertIsNotNone(rec.pk)

    def test_multiple_courses_same_day(self):
        """A student can have separate attendance rows for two different courses on the same day."""
        today = localdate()
        now = localtime()
        rec_a = StudentAttendanceRecord.objects.create(
            student=self.student,
            date=today,
            check_in_time=now,
            original_teacher=self.teacher_a,
            assigned_teacher=self.teacher_a,
        )
        rec_b = StudentAttendanceRecord.objects.create(
            student=self.student,
            date=today,
            check_in_time=now,
            original_teacher=self.teacher_b,
            assigned_teacher=self.teacher_b,
        )
        self.assertNotEqual(rec_a.pk, rec_b.pk)
        self.assertEqual(
            StudentAttendanceRecord.objects.filter(
                student=self.student, date=today
            ).count(),
            2,
        )

    def test_duplicate_same_course_same_day_raises(self):
        """Creating a second record for the same student+date+course raises IntegrityError."""
        today = localdate()
        now = localtime()
        StudentAttendanceRecord.objects.create(
            student=self.student,
            date=today,
            check_in_time=now,
            original_teacher=self.teacher_a,
            assigned_teacher=self.teacher_a,
        )
        with self.assertRaises(IntegrityError):
            StudentAttendanceRecord.objects.create(
                student=self.student,
                date=today,
                check_in_time=now,
                original_teacher=self.teacher_a,
                assigned_teacher=self.teacher_a,
            )

    def test_no_course_guard_prevents_duplicate_null_teacher(self):
        """Two records with original_teacher=None on the same day for the same student raises IntegrityError."""
        today = localdate()
        now = localtime()
        StudentAttendanceRecord.objects.create(
            student=self.student,
            date=today,
            check_in_time=now,
            original_teacher=None,
            assigned_teacher=None,
        )
        with self.assertRaises(IntegrityError):
            StudentAttendanceRecord.objects.create(
                student=self.student,
                date=today,
                check_in_time=now,
                original_teacher=None,
                assigned_teacher=None,
            )

    def test_no_course_and_course_same_day_allowed(self):
        """A record with original_teacher=None and one with a teacher can coexist on the same day."""
        today = localdate()
        now = localtime()
        rec_none = StudentAttendanceRecord.objects.create(
            student=self.student,
            date=today,
            check_in_time=now,
            original_teacher=None,
            assigned_teacher=None,
        )
        rec_a = StudentAttendanceRecord.objects.create(
            student=self.student,
            date=today,
            check_in_time=now,
            original_teacher=self.teacher_a,
            assigned_teacher=self.teacher_a,
        )
        self.assertNotEqual(rec_none.pk, rec_a.pk)


class StationSessionTeacherTestCase(TestCase):
    """Test scan station behavior with session_teacher (course dropdown)."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_user(
            phone='01100000001',
            email='admin-st@test.com',
            password='pass123',
            role=User.Role.ADMIN,
        )
        cls.course_teacher = Teacher.objects.create(
            user=User.objects.create_user(
                phone='01100000002', email='course@test.com',
                password='pass123', role=User.Role.TEACHER,
            ),
            full_name='Course Math',
            subject='رياضيات',
            is_course=True,
        )
        cls.primary_teacher = Teacher.objects.create(
            user=User.objects.create_user(
                phone='01100000003', email='primary@test.com',
                password='pass123', role=User.Role.TEACHER,
            ),
            full_name='Primary Teacher',
            is_course=False,
        )
        cls.student = Student.objects.create(
            national_id='NID_STATION_01',
            full_name='Student Station Test',
            student_code='STN001',
        )
        StudentTeacherLink.objects.create(
            student=cls.student,
            teacher=cls.primary_teacher,
            is_primary=True,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(phone='01100000001', password='pass123')
        self.scan_url = reverse('attendance:station')

    def test_checkin_with_session_teacher(self):
        """Scanning a student with a selected course creates a record with that original_teacher."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.student.id),
            'session_teacher': str(self.course_teacher.id),
        })
        self.assertEqual(response.status_code, 200)
        rec = StudentAttendanceRecord.objects.get(
            student=self.student,
            date=localdate(),
            original_teacher=self.course_teacher,
        )
        self.assertEqual(rec.assigned_teacher, self.course_teacher)

    def test_checkin_automatic_mode_uses_primary_link(self):
        """Scanning without a course selected uses the primary link teacher."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.student.id),
            'session_teacher': '',
        })
        self.assertEqual(response.status_code, 200)
        rec = StudentAttendanceRecord.objects.get(
            student=self.student,
            date=localdate(),
            original_teacher=self.primary_teacher,
        )
        self.assertEqual(rec.assigned_teacher, self.primary_teacher)

    def test_checkout_with_session_teacher(self):
        """Second scan with the same course checks out the correct record."""
        today = localdate()
        check_in = localtime() - timedelta(minutes=10)
        StudentAttendanceRecord.objects.create(
            student=self.student,
            date=today,
            check_in_time=check_in,
            original_teacher=self.course_teacher,
            assigned_teacher=self.course_teacher,
            recorded_by=self.admin_user,
        )
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.student.id),
            'session_teacher': str(self.course_teacher.id),
        })
        self.assertEqual(response.status_code, 200)
        rec = StudentAttendanceRecord.objects.get(
            student=self.student,
            date=today,
            original_teacher=self.course_teacher,
        )
        self.assertIsNotNone(rec.check_out_time)

    def test_checkout_automatic_mode(self):
        """Second scan without a course uses the primary link teacher to find the correct record."""
        today = localdate()
        check_in = localtime() - timedelta(minutes=10)
        StudentAttendanceRecord.objects.create(
            student=self.student,
            date=today,
            check_in_time=check_in,
            original_teacher=self.primary_teacher,
            assigned_teacher=self.primary_teacher,
            recorded_by=self.admin_user,
        )
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.student.id),
            'session_teacher': '',
        })
        self.assertEqual(response.status_code, 200)
        rec = StudentAttendanceRecord.objects.get(
            student=self.student,
            date=today,
            original_teacher=self.primary_teacher,
        )
        self.assertIsNotNone(rec.check_out_time)

    def test_multi_course_checkin_same_student(self):
        """A student can check in to two different courses on the same day via separate scans."""
        # First scan — course
        self.client.post(self.scan_url, {
            'scanned_codes': str(self.student.id),
            'session_teacher': str(self.course_teacher.id),
        })
        # Second scan — automatic (primary teacher)
        self.client.post(self.scan_url, {
            'scanned_codes': str(self.student.id),
            'session_teacher': '',
        })
        today = localdate()
        self.assertEqual(
            StudentAttendanceRecord.objects.filter(
                student=self.student, date=today
            ).count(),
            2,
        )

    def test_session_teacher_sticky_in_context(self):
        """The selected course is passed back in context so the dropdown stays selected."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.student.id),
            'session_teacher': str(self.course_teacher.id),
        })
        self.assertEqual(
            response.context['session_teacher_id'],
            str(self.course_teacher.id),
        )

    def test_courses_in_context(self):
        """The courses queryset is passed to the template context."""
        response = self.client.get(self.scan_url)
        self.assertIn('courses', response.context)
        course_ids = list(response.context['courses'].values_list('id', flat=True))
        self.assertIn(self.course_teacher.id, course_ids)
        # Non-course teacher should not appear
        self.assertNotIn(self.primary_teacher.id, course_ids)


class IsCourseFieldTestCase(TestCase):
    """Test the is_course field on Teacher model."""

    def test_default_is_false(self):
        """New teachers default to is_course=False."""
        user = User.objects.create_user(
            phone='01200000001', email='def@test.com',
            password='pass', role=User.Role.TEACHER,
        )
        teacher = Teacher.objects.create(user=user, full_name='Regular Teacher')
        self.assertFalse(teacher.is_course)

    def test_can_set_to_true(self):
        """Can explicitly set is_course=True."""
        user = User.objects.create_user(
            phone='01200000002', email='course2@test.com',
            password='pass', role=User.Role.TEACHER,
        )
        teacher = Teacher.objects.create(
            user=user, full_name='Course XYZ', is_course=True
        )
        self.assertTrue(teacher.is_course)
        teacher.refresh_from_db()
        self.assertTrue(teacher.is_course)
