"""
Tests for attendance and teacher scan views.

This module contains tests for:
- Scan station (admin-only access)
- Teacher scan endpoint (scans only linked students)
"""

import uuid
from django.test import TestCase, Client
from django.urls import reverse

from core.models import User, Student, Teacher, StudentTeacherLink
from attendance.models import StudentAttendanceRecord
from django.utils.timezone import localdate


class ScanStationPermissionTestCase(TestCase):
    """Test cases for scan station admin-only access."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all test methods."""
        cls.admin_user = User.objects.create_user(
            phone='01234567890',
            email='admin@test.com',
            password='adminpass123',
            role=User.Role.ADMIN,
            first_name='Test',
            last_name='Admin'
        )

        cls.teacher_user = User.objects.create_user(
            phone='01234567891',
            email='teacher@test.com',
            password='teacherpass123',
            role=User.Role.TEACHER,
            first_name='Test',
            last_name='Teacher'
        )

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.scan_url = reverse('attendance:station')

    def test_scan_page_requires_login(self):
        """Test that scan station requires login."""
        response = self.client.get(self.scan_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_admin_can_access_scan_station(self):
        """Test that admin can access scan station."""
        self.client.login(phone='01234567890', password='adminpass123')
        response = self.client.get(self.scan_url)
        self.assertEqual(response.status_code, 200)

    def test_teacher_cannot_access_scan_station(self):
        """Test that teacher cannot access scan station."""
        self.client.login(phone='01234567891', password='teacherpass123')
        response = self.client.get(self.scan_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/', response.url)


class TeacherScanTestCase(TestCase):
    """Test cases for teacher scan endpoint."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.teacher_user = User.objects.create_user(
            phone='01234567891',
            email='teacher@test.com',
            password='teacherpass123',
            role=User.Role.TEACHER,
            first_name='Test',
            last_name='Teacher'
        )

        cls.teacher_obj = Teacher.objects.create(user=cls.teacher_user)

        # Students linked to teacher
        cls.linked_student1 = Student.objects.create(
            full_name='Linked Student 1',
            national_id='12345678901234',
            student_code='STU001'
        )

        cls.linked_student2 = Student.objects.create(
            full_name='Linked Student 2',
            national_id='12345678901235',
            student_code='STU002'
        )

        # Student NOT linked to teacher
        cls.unlinked_student = Student.objects.create(
            full_name='Unlinked Student',
            national_id='12345678901236',
            student_code='STU999'
        )

        # Create teacher-student links
        StudentTeacherLink.objects.create(
            student=cls.linked_student1,
            teacher=cls.teacher_obj,
            is_primary=True
        )
        StudentTeacherLink.objects.create(
            student=cls.linked_student2,
            teacher=cls.teacher_obj,
            is_primary=True
        )

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.teacher_url = reverse('teacher_portal:dashboard')
        self.scan_url = reverse('teacher_portal:scan')
        self.client.login(phone='01234567891', password='teacherpass123')

    def test_teacher_can_scan_linked_students_by_uuid(self):
        """Test teacher can scan a linked student by UUID."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.linked_student1.id)
        })

        # Should redirect back to teacher dashboard
        self.assertEqual(response.status_code, 302)
        self.assertIn('portal/teacher', response.url)

        # Verify attendance record was created
        self.assertTrue(
            StudentAttendanceRecord.objects.filter(
                student=self.linked_student1,
                date=localdate()
            ).exists()
        )

    def test_teacher_can_scan_linked_students_by_code(self):
        """Test teacher can scan a linked student by student_code."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': 'STU001'
        })

        self.assertEqual(response.status_code, 302)

        # Verify attendance record was created
        self.assertTrue(
            StudentAttendanceRecord.objects.filter(
                student=self.linked_student1,
                date=localdate()
            ).exists()
        )

    def test_teacher_can_scan_linked_students_by_national_id(self):
        """Test teacher can scan a linked student by national_id."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': '12345678901235'
        })

        self.assertEqual(response.status_code, 302)

        # Verify attendance record was created
        self.assertTrue(
            StudentAttendanceRecord.objects.filter(
                student=self.linked_student2,
                date=localdate()
            ).exists()
        )

    def test_teacher_cannot_scan_unlinked_students(self):
        """Test that teacher cannot scan unlinked students."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.unlinked_student.id)
        })

        self.assertEqual(response.status_code, 302)

        # Verify NO attendance record was created
        self.assertFalse(
            StudentAttendanceRecord.objects.filter(
                student=self.unlinked_student,
                date=localdate()
            ).exists()
        )

    def test_teacher_can_scan_multiple_linked_students(self):
        """Test teacher can scan multiple linked students at once."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': f'{self.linked_student1.id}\n{self.linked_student2.id}'
        })

        self.assertEqual(response.status_code, 302)

        # Verify both records were created
        self.assertEqual(
            StudentAttendanceRecord.objects.filter(
                date=localdate()
            ).count(),
            2
        )

    def test_teacher_scan_duplicate_prevention(self):
        """Test that scanning same student twice only creates one record."""
        # First scan
        self.client.post(self.scan_url, {
            'scanned_codes': str(self.linked_student1.id)
        })

        # Second scan of same student
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.linked_student1.id)
        })

        self.assertEqual(response.status_code, 302)

        # Verify only one record exists
        self.assertEqual(
            StudentAttendanceRecord.objects.filter(
                student=self.linked_student1,
                date=localdate()
            ).count(),
            1
        )

    def test_teacher_scan_recorded_by_teacher(self):
        """Test that teacher's scan is recorded with teacher as recorded_by."""
        self.client.post(self.scan_url, {
            'scanned_codes': str(self.linked_student1.id)
        })

        record = StudentAttendanceRecord.objects.get(
            student=self.linked_student1,
            date=localdate()
        )

        self.assertEqual(record.recorded_by, self.teacher_user)

    def test_teacher_cannot_access_endpoint_if_not_logged_in(self):
        """Test that unauthenticated user cannot access teacher scan."""
        self.client.logout()
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.linked_student1.id)
        })

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)


class ScanStationAdminScansTestCase(TestCase):
    """Test cases for admin scan functionality."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.admin_user = User.objects.create_user(
            phone='01234567890',
            email='admin@test.com',
            password='adminpass123',
            role=User.Role.ADMIN,
            first_name='Test',
            last_name='Admin'
        )

        cls.student = Student.objects.create(
            full_name='Test Student',
            national_id='12345678901234',
            student_code='TST001'
        )

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.scan_url = reverse('attendance:station')
        self.client.login(phone='01234567890', password='adminpass123')

    def test_admin_can_scan_any_student(self):
        """Test that admin can scan any student in the system."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.student.id)
        })

        self.assertEqual(response.status_code, 200)

        # Verify attendance record was created
        self.assertTrue(
            StudentAttendanceRecord.objects.filter(
                student=self.student,
                date=localdate()
            ).exists()
        )

    def test_admin_scan_by_student_code(self):
        """Test admin can scan by student_code."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': 'TST001'
        })

        self.assertEqual(response.status_code, 200)

        self.assertTrue(
            StudentAttendanceRecord.objects.filter(
                student=self.student,
                date=localdate()
            ).exists()
        )
