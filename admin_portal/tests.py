# Tests live in admin_portal/tests/ — this file is shadowed by that package.

from django.urls import reverse
from django.utils.timezone import localdate, localtime

from core.models import User, Student, Teacher
from attendance.models import StudentAttendanceRecord, TeacherAttendanceRecord


class AdminDashboardTestCase(TestCase):
    """Test cases for the admin dashboard view."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_user(
            phone='01234567890', email='admin@test.com', password='adminpass123',
            role=User.Role.ADMIN, first_name='Test', last_name='Admin'
        )
        cls.teacher_user = User.objects.create_user(
            phone='01234567891', email='teacher@test.com', password='teacherpass123',
            role=User.Role.TEACHER, first_name='Test', last_name='Teacher'
        )
        cls.teacher_obj = Teacher.objects.create(
            user=cls.teacher_user, full_name='Test Teacher'
        )
        cls.student1 = Student.objects.create(
            full_name='Student One', national_id='12345678901234', student_code='STU001'
        )
        cls.student2 = Student.objects.create(
            full_name='Student Two', national_id='12345678901235', student_code='STU002'
        )

    def setUp(self):
        self.client = Client()
        self.url = reverse('admin_portal:dashboard')

    # ---------- access control ----------

    def test_admin_can_access_dashboard(self):
        self.client.login(phone='01234567890', password='adminpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_teacher_cannot_access_admin_dashboard(self):
        self.client.login(phone='01234567891', password='teacherpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    # ---------- context totals ----------

    def test_context_total_students_and_teachers(self):
        self.client.login(phone='01234567890', password='adminpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.context['total_students'], 2)
        self.assertEqual(response.context['total_teachers'], 1)

    def test_context_today_attendance_counts(self):
        StudentAttendanceRecord.objects.create(
            student=self.student1, date=localdate(), check_in_time=localtime(),
            recorded_by=self.admin_user,
        )
        TeacherAttendanceRecord.objects.create(
            teacher=self.teacher_obj, date=localdate(), check_in_time=localtime(),
            recorded_by=self.admin_user,
        )
        self.client.login(phone='01234567890', password='adminpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.context['today_student_attendance_count'], 1)
        self.assertEqual(response.context['today_teacher_attendance_count'], 1)

    def test_context_zero_when_no_attendance_today(self):
        self.client.login(phone='01234567890', password='adminpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.context['today_student_attendance_count'], 0)
        self.assertEqual(response.context['today_teacher_attendance_count'], 0)

    # ---------- missing photos ----------

    def test_missing_photos_counts_null_records(self):
        """Records created without a photo (daily_photo=NULL) are counted."""
        StudentAttendanceRecord.objects.create(
            student=self.student1, date=localdate(), check_in_time=localtime(),
            recorded_by=self.admin_user, daily_photo=None,
        )
        self.client.login(phone='01234567890', password='adminpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.context['today_missing_photos_count'], 1)

    def test_missing_photos_counts_empty_string_records(self):
        """Records where photo was cleared (daily_photo='') are also counted."""
        StudentAttendanceRecord.objects.create(
            student=self.student1, date=localdate(), check_in_time=localtime(),
            recorded_by=self.admin_user, daily_photo='',
        )
        self.client.login(phone='01234567890', password='adminpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.context['today_missing_photos_count'], 1)

    # ---------- substitute count ----------

    def test_substitute_count_when_assigned_differs_from_original(self):
        other_teacher_user = User.objects.create_user(
            phone='01234567892', email='t2@test.com', password='t2pass',
            role=User.Role.TEACHER, first_name='Other', last_name='Teacher'
        )
        other_teacher = Teacher.objects.create(
            user=other_teacher_user, full_name='Other Teacher'
        )
        StudentAttendanceRecord.objects.create(
            student=self.student1, date=localdate(), check_in_time=localtime(),
            recorded_by=self.admin_user,
            original_teacher=self.teacher_obj,
            assigned_teacher=other_teacher,
        )
        self.client.login(phone='01234567890', password='adminpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.context['today_substitute_count'], 1)

    def test_substitute_count_zero_when_same_teacher(self):
        StudentAttendanceRecord.objects.create(
            student=self.student1, date=localdate(), check_in_time=localtime(),
            recorded_by=self.admin_user,
            original_teacher=self.teacher_obj,
            assigned_teacher=self.teacher_obj,
        )
        self.client.login(phone='01234567890', password='adminpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.context['today_substitute_count'], 0)
