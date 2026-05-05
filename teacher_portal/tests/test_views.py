import uuid

from django.test import TestCase, Client
from django.urls import reverse

from core.models import User, Student, Teacher, StudentTeacherLink
from attendance.models import StudentAttendanceRecord


class StudentHistoryTeacherPortalTestCase(TestCase):
    """Tests for teacher_portal:student_history view."""

    @classmethod
    def setUpTestData(cls):
        # Teacher who owns the student
        cls.teacher_user = User.objects.create_user(
            phone='01700000001', email='teacher1@hist.com', password='pass',
            role=User.Role.TEACHER,
        )
        cls.teacher = Teacher.objects.create(
            user=cls.teacher_user, full_name='معلم السجل',
        )

        # Another teacher who does NOT own the student
        cls.other_teacher_user = User.objects.create_user(
            phone='01700000002', email='teacher2@hist.com', password='pass',
            role=User.Role.TEACHER,
        )
        cls.other_teacher = Teacher.objects.create(
            user=cls.other_teacher_user, full_name='معلم آخر',
        )

        # Admin user (must NOT access teacher portal student_history)
        cls.admin_user = User.objects.create_user(
            phone='01700000003', email='admin@hist.com', password='pass',
            role=User.Role.ADMIN,
        )

        cls.student = Student.objects.create(
            full_name='طالب السجل', national_id='30000000000001',
            student_code='TH001', grade='الصف الأول',
        )
        StudentTeacherLink.objects.create(
            teacher=cls.teacher, student=cls.student, is_primary=True,
        )

        # Unlinked student (not linked to cls.teacher)
        cls.other_student = Student.objects.create(
            full_name='طالب غير مرتبط', national_id='30000000000002',
            student_code='TH002',
        )
        StudentTeacherLink.objects.create(
            teacher=cls.other_teacher, student=cls.other_student,
        )

        # Two attendance records on different dates
        cls.record_newer = StudentAttendanceRecord.objects.create(
            student=cls.student,
            date='2025-03-15',
            check_in_time='2025-03-15 08:10:00',
            assigned_teacher=cls.teacher,
            original_teacher=cls.teacher,
            rating=9,
        )
        cls.record_older = StudentAttendanceRecord.objects.create(
            student=cls.student,
            date='2025-03-10',
            check_in_time='2025-03-10 08:00:00',
            assigned_teacher=cls.teacher,
            original_teacher=cls.teacher,
            rating=7,
        )

        # A record that is a substitute assignment (different assigned/original)
        cls.substitute_record = StudentAttendanceRecord.objects.create(
            student=cls.student,
            date='2025-03-20',
            check_in_time='2025-03-20 08:05:00',
            assigned_teacher=cls.other_teacher,
            original_teacher=cls.teacher,
            rating=8,
            substitute_note='غياب المعلم الأصلي',
        )

    def setUp(self):
        self.client = Client()
        self.client.login(phone='01700000001', password='pass')
        self.url = reverse('teacher_portal:student_history', args=[self.student.id])

    # --- access control ---

    def test_linked_teacher_can_access(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_unlinked_teacher_gets_404(self):
        self.client.logout()
        self.client.login(phone='01700000002', password='pass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_redirected(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_admin_cannot_access_teacher_portal(self):
        self.client.logout()
        self.client.login(phone='01700000003', password='pass')
        response = self.client.get(self.url)
        # Admin users are not teachers — should be redirected
        self.assertEqual(response.status_code, 302)

    def test_nonexistent_student_returns_404(self):
        url = reverse('teacher_portal:student_history', args=[uuid.uuid4()])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # --- context ---

    def test_context_contains_student(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context['student'], self.student)

    def test_context_total_records(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context['total_records'], 3)

    def test_context_records_ordered_desc_by_date(self):
        response = self.client.get(self.url)
        records = list(response.context['records'])
        dates = [r.date.isoformat() for r in records]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_newest_record_first(self):
        response = self.client.get(self.url)
        records = list(response.context['records'])
        self.assertEqual(records[0].date.isoformat(), '2025-03-20')

    # --- template content ---

    def test_student_name_in_response(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'طالب السجل')

    def test_substitute_indicator_shown(self):
        response = self.client.get(self.url)
        # The substitute record row should be highlighted (table-warning class present)
        self.assertContains(response, 'table-warning')
        # The substitute note should reference the original teacher
        self.assertContains(response, 'معلم السجل')

    def test_empty_state_when_no_records(self):
        # Create a student with no records, linked to teacher
        empty_student = Student.objects.create(
            full_name='طالب بلا سجل', national_id='30000000000099',
            student_code='TH099',
        )
        StudentTeacherLink.objects.create(teacher=self.teacher, student=empty_student)
        url = reverse('teacher_portal:student_history', args=[empty_student.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_records'], 0)
        self.assertContains(response, 'لا يوجد سجل حضور')
