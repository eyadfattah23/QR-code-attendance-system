"""
Tests for attendance and teacher scan views.

This module contains tests for:
- Scan station (admin-only access)
- Teacher scan endpoint (scans only linked students)
"""

import uuid
from django.contrib.messages import get_messages
from django.test import TestCase, Client
from django.urls import reverse

from core.models import User, Student, Teacher, StudentTeacherLink
from attendance.models import StudentAttendanceRecord, TeacherAttendanceRecord
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

        cls.teacher_obj = Teacher.objects.create(
            user=cls.teacher_user,
            full_name='Test Teacher'
        )

        # Another teacher — used to test scanning a teacher UUID from teacher portal
        cls.teacher_user_2 = User.objects.create_user(
            phone='01234567892',
            email='teacher2@test.com',
            password='teacher2pass123',
            role=User.Role.TEACHER,
            first_name='Another',
            last_name='Teacher'
        )
        cls.another_teacher = Teacher.objects.create(
            user=cls.teacher_user_2,
            full_name='Another Teacher'
        )

        # Admin user — used to verify admin cannot hit teacher scan endpoint
        cls.admin_user = User.objects.create_user(
            phone='01234567890',
            email='admin@test.com',
            password='adminpass123',
            role=User.Role.ADMIN,
            first_name='Test',
            last_name='Admin'
        )

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

    def test_admin_cannot_use_teacher_scan_endpoint(self):
        """Test that an admin user is redirected away from the teacher scan endpoint."""
        self.client.logout()
        self.client.login(phone='01234567890', password='adminpass123')
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.linked_student1.id)
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            StudentAttendanceRecord.objects.filter(
                student=self.linked_student1,
                date=localdate()
            ).exists()
        )

    def test_teacher_scan_empty_input_shows_warning(self):
        """Test that submitting no codes produces a warning message."""
        response = self.client.post(self.scan_url, {'scanned_codes': ''})
        self.assertEqual(response.status_code, 302)
        messages_list = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages_list), 1)
        self.assertEqual(messages_list[0].level_tag, 'warning')

    def test_teacher_scan_unknown_code_not_in_db(self):
        """Test scanning a code that matches no student shows an error message."""
        response = self.client.post(
            self.scan_url, {'scanned_codes': 'NOEXIST999'})
        self.assertEqual(response.status_code, 302)
        messages_list = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages_list), 1)
        self.assertEqual(messages_list[0].level_tag, 'error')
        self.assertIn('لم يتم العثور', str(messages_list[0]))

    def test_teacher_scan_unknown_uuid_not_in_db(self):
        """Test scanning a valid UUID matching no record shows an error message."""
        unknown_uuid = str(uuid.uuid4())
        response = self.client.post(
            self.scan_url, {'scanned_codes': unknown_uuid})
        self.assertEqual(response.status_code, 302)
        messages_list = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages_list), 1)
        self.assertEqual(messages_list[0].level_tag, 'error')

    def test_teacher_scan_teacher_uuid_shows_warning_not_record(self):
        """Test scanning another teacher's UUID produces a warning and no TeacherAttendanceRecord."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.another_teacher.id)
        })
        self.assertEqual(response.status_code, 302)
        messages_list = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages_list), 1)
        self.assertEqual(messages_list[0].level_tag, 'warning')
        # No teacher record should have been created
        self.assertFalse(
            TeacherAttendanceRecord.objects.filter(
                teacher=self.another_teacher,
                date=localdate()
            ).exists()
        )

    def test_teacher_scan_unlinked_student_message_differs_from_not_found(self):
        """Unlinked student error includes student name; not-found error uses generic phrase."""
        # Use separate clients so session messages don't bleed across requests
        client_a = Client()
        client_a.login(phone='01234567891', password='teacherpass123')
        response_unlinked = client_a.post(self.scan_url, {
            'scanned_codes': str(self.unlinked_student.id)
        })
        msgs_unlinked = list(get_messages(response_unlinked.wsgi_request))
        unlinked_text = str(msgs_unlinked[0])

        client_b = Client()
        client_b.login(phone='01234567891', password='teacherpass123')
        response_unknown = client_b.post(
            self.scan_url, {'scanned_codes': 'NO-SUCH-CODE'})
        msgs_unknown = list(get_messages(response_unknown.wsgi_request))
        unknown_text = str(msgs_unknown[0])

        # Unlinked message contains the student's name
        self.assertIn(self.unlinked_student.full_name, unlinked_text)
        # Not-found message contains the generic Arabic phrase
        self.assertIn('لم يتم العثور', unknown_text)
        # The two messages are different
        self.assertNotEqual(unlinked_text, unknown_text)


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

        # Teacher for admin-scan-teacher tests
        cls.teacher_user = User.objects.create_user(
            phone='01234567891',
            email='teacher@test.com',
            password='teacherpass123',
            role=User.Role.TEACHER,
            first_name='Test',
            last_name='Teacher'
        )
        cls.teacher_for_scan = Teacher.objects.create(
            user=cls.teacher_user,
            full_name='Test Teacher For Scan'
        )

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.scan_url = reverse('attendance:station')
        self.client.login(phone='01234567890', password='adminpass123')

    def test_admin_scan_by_uuid(self):
        """Test admin can scan by student UUID."""
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

    def test_admin_scan_by_national_id(self):
        """Test admin can scan by national_id."""
        response = self.client.post(
            self.scan_url, {'scanned_codes': '12345678901234'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            StudentAttendanceRecord.objects.filter(
                student=self.student,
                date=localdate()
            ).exists()
        )

    def test_admin_scan_teacher_uuid_creates_teacher_record(self):
        """Test admin scanning a teacher UUID creates a TeacherAttendanceRecord."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.teacher_for_scan.id)
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            TeacherAttendanceRecord.objects.filter(
                teacher=self.teacher_for_scan,
                date=localdate()
            ).exists()
        )

    def test_admin_scan_teacher_result_is_success(self):
        """Test admin scan of teacher UUID shows success result."""
        response = self.client.post(self.scan_url, {
            'scanned_codes': str(self.teacher_for_scan.id)
        })
        results = response.context['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['status'], 'success')
        self.assertIn(self.teacher_for_scan.full_name, results[0]['message'])

    def test_admin_scan_already_scanned_student_shows_warning(self):
        """Test scanning an already-scanned student shows warning result."""
        self.client.post(
            self.scan_url, {'scanned_codes': str(self.student.id)})
        response = self.client.post(
            self.scan_url, {'scanned_codes': str(self.student.id)})
        results = response.context['results']
        self.assertEqual(results[0]['status'], 'warning')

    def test_admin_scan_already_scanned_teacher_shows_warning(self):
        """Test scanning an already-scanned teacher shows warning result."""
        self.client.post(
            self.scan_url, {'scanned_codes': str(self.teacher_for_scan.id)})
        response = self.client.post(
            self.scan_url, {'scanned_codes': str(self.teacher_for_scan.id)})
        results = response.context['results']
        self.assertEqual(results[0]['status'], 'warning')

    def test_admin_scan_unknown_code_shows_error(self):
        """Test scanning an unknown non-UUID code shows error result."""
        response = self.client.post(
            self.scan_url, {'scanned_codes': 'UNKNOWN-CODE-XYZ'})
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['status'], 'error')

    def test_admin_scan_unknown_uuid_shows_error(self):
        """Test scanning a valid UUID that matches no record shows error result."""
        unknown_uuid = str(uuid.uuid4())
        response = self.client.post(
            self.scan_url, {'scanned_codes': unknown_uuid})
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['status'], 'error')

    def test_admin_scan_empty_input_no_results(self):
        """Test empty input produces no results."""
        response = self.client.post(self.scan_url, {'scanned_codes': ''})
        self.assertEqual(response.status_code, 200)
        results = response.context.get('results', [])
        self.assertEqual(len(results), 0)

    def test_admin_scan_result_context_counts(self):
        """Test mixed batch: success + warning (duplicate) + error gives correct counts."""
        # Pre-scan teacher to force a warning on second attempt
        self.client.post(
            self.scan_url, {'scanned_codes': str(self.teacher_for_scan.id)})

        batch = '\n'.join([
            str(self.student.id),           # success
            str(self.teacher_for_scan.id),  # warning (already scanned)
            'TOTALLY-UNKNOWN-CODE',          # error
        ])
        response = self.client.post(self.scan_url, {'scanned_codes': batch})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['success_count'], 1)
        self.assertEqual(response.context['warning_count'], 1)
        self.assertEqual(response.context['error_count'], 1)
        self.assertEqual(response.context['total_count'], 3)
