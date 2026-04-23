from io import BytesIO

import openpyxl
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils.timezone import localdate, localtime

from core.models import User, Student, Teacher
from attendance.models import StudentAttendanceRecord, TeacherAttendanceRecord


def _make_excel_upload(rows):
    """Build a SimpleUploadedFile from a list of row tuples (openpyxl)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(list(row))
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return SimpleUploadedFile(
        'students.xlsx',
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


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


# ---------------------------------------------------------------------------
# Student management tests
# ---------------------------------------------------------------------------

class _StudentManagementBase(TestCase):
    """Shared fixtures for student management test cases."""

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
        cls.student = Student.objects.create(
            full_name='Existing Student',
            national_id='12345678901234',
            student_code='STU001',
            grade='الصف الأول',
        )

    def setUp(self):
        self.client = Client()
        self.client.login(phone='01234567890', password='adminpass123')


class StudentListTestCase(_StudentManagementBase):
    """Tests for student_list view."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Extra students for pagination (25/page → need >25 total)
        for i in range(30):
            Student.objects.create(
                full_name=f'Bulk Student {i:02d}',
                national_id=f'{i:014d}',
                student_code=f'BLK{i:04d}',
            )
        cls.grade_b_student = Student.objects.create(
            full_name='Grade B Student',
            national_id='99999999999999',
            student_code='GRDB001',
            grade='الصف الثاني',
        )

    def setUp(self):
        super().setUp()
        self.url = reverse('admin_portal:student_list')

    def test_admin_can_access_list(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_teacher_cannot_access_list(self):
        self.client.logout()
        self.client.login(phone='01234567891', password='teacherpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_unauthenticated_redirected(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_search_by_name(self):
        response = self.client.get(self.url, {'q': 'Existing Student'})
        students = list(response.context['page_obj'])
        self.assertEqual(len(students), 1)
        self.assertEqual(students[0].full_name, 'Existing Student')

    def test_search_by_national_id(self):
        response = self.client.get(self.url, {'q': '12345678901234'})
        students = list(response.context['page_obj'])
        self.assertEqual(len(students), 1)

    def test_search_by_student_code(self):
        response = self.client.get(self.url, {'q': 'STU001'})
        students = list(response.context['page_obj'])
        self.assertEqual(len(students), 1)

    def test_filter_by_grade(self):
        response = self.client.get(self.url, {'grade': 'الصف الثاني'})
        students = list(response.context['page_obj'])
        self.assertEqual(len(students), 1)
        self.assertEqual(students[0].full_name, 'Grade B Student')

    def test_first_page_has_25_students(self):
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['page_obj'].object_list), 25)

    def test_total_count_is_correct(self):
        response = self.client.get(self.url)
        # 1 existing + 30 bulk + 1 grade_b = 32
        self.assertEqual(response.context['total_count'], 32)


class StudentCreateTestCase(_StudentManagementBase):
    """Tests for student_create view."""

    def setUp(self):
        super().setUp()
        self.url = reverse('admin_portal:student_create')

    def test_get_shows_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)

    def test_create_valid_student(self):
        response = self.client.post(self.url, {
            'full_name': 'New Student',
            'national_id': '99999999999999',
            'student_code': 'NEW001',
            'grade': 'الصف الثاني',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Student.objects.filter(
            national_id='99999999999999').exists())

    def test_create_redirects_to_list(self):
        response = self.client.post(self.url, {
            'full_name': 'Another Student',
            'national_id': '88888888888888',
            'student_code': '',
            'grade': '',
        })
        self.assertRedirects(response, reverse('admin_portal:student_list'))

    def test_create_duplicate_national_id_rejected(self):
        response = self.client.post(self.url, {
            'full_name': 'Duplicate',
            'national_id': '12345678901234',  # already exists
            'student_code': 'DUP001',
            'grade': '',
        })
        # form re-rendered with errors
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Student.objects.filter(
            student_code='DUP001').exists())

    def test_create_auto_fills_student_code_from_national_id(self):
        self.client.post(self.url, {
            'full_name': 'Auto Code Student',
            'national_id': '77777777777777',
            'student_code': '',
            'grade': '',
        })
        student = Student.objects.get(national_id='77777777777777')
        self.assertEqual(student.student_code, '77777777777777')

    def test_teacher_cannot_access_create(self):
        self.client.logout()
        self.client.login(phone='01234567891', password='teacherpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)


class StudentEditTestCase(_StudentManagementBase):
    """Tests for student_edit view."""

    def setUp(self):
        super().setUp()
        self.url = reverse('admin_portal:student_edit', args=[self.student.id])

    def test_get_shows_form_populated(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].instance.pk, self.student.pk)

    def test_edit_updates_student(self):
        self.client.post(self.url, {
            'full_name': 'Updated Name',
            'national_id': '12345678901234',
            'student_code': 'STU001',
            'grade': 'الصف الثاني',
        })
        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, 'Updated Name')
        self.assertEqual(self.student.grade, 'الصف الثاني')

    def test_edit_redirects_to_list(self):
        response = self.client.post(self.url, {
            'full_name': 'Updated Name',
            'national_id': '12345678901234',
            'student_code': 'STU001',
            'grade': '',
        })
        self.assertRedirects(response, reverse('admin_portal:student_list'))

    def test_edit_nonexistent_student_returns_404(self):
        import uuid
        url = reverse('admin_portal:student_edit', args=[uuid.uuid4()])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class StudentDeleteTestCase(_StudentManagementBase):
    """Tests for student_delete view."""

    def test_delete_removes_student(self):
        new_student = Student.objects.create(
            full_name='To Delete',
            national_id='55555555555555',
            student_code='DEL001',
        )
        url = reverse('admin_portal:student_delete', args=[new_student.id])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('admin_portal:student_list'))
        self.assertFalse(Student.objects.filter(pk=new_student.pk).exists())

    def test_delete_nonexistent_returns_404(self):
        import uuid
        url = reverse('admin_portal:student_delete', args=[uuid.uuid4()])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_delete_requires_post(self):
        url = reverse('admin_portal:student_delete', args=[self.student.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)


class StudentImportTestCase(_StudentManagementBase):
    """Tests for student_import and student_import_template views."""

    def setUp(self):
        super().setUp()
        self.url = reverse('admin_portal:student_import')

    def test_import_valid_excel_creates_students(self):
        upload = _make_excel_upload([
            ('full_name', 'national_id', 'student_code', 'grade'),
            ('Import Student One', '11111111111111', 'IMP001', 'الصف الثالث'),
            ('Import Student Two', '22222222222222', 'IMP002', ''),
        ])
        self.client.post(self.url, {'excel_file': upload})
        self.assertTrue(Student.objects.filter(
            national_id='11111111111111').exists())
        self.assertTrue(Student.objects.filter(
            national_id='22222222222222').exists())

    def test_import_duplicate_national_id_skipped(self):
        before = Student.objects.count()
        upload = _make_excel_upload([
            ('full_name', 'national_id'),
            ('Duplicate', '12345678901234'),  # already exists
        ])
        self.client.post(self.url, {'excel_file': upload})
        self.assertEqual(Student.objects.count(), before)

    def test_import_missing_required_headers_rejected(self):
        upload = _make_excel_upload([
            ('name', 'id'),  # wrong header names
            ('Someone', '11111111111111'),
        ])
        response = self.client.post(self.url, {'excel_file': upload})
        self.assertRedirects(response, reverse('admin_portal:student_list'))
        self.assertFalse(Student.objects.filter(
            national_id='11111111111111').exists())

    def test_import_no_file_redirects_with_error(self):
        response = self.client.post(self.url, {})
        self.assertRedirects(response, reverse('admin_portal:student_list'))

    def test_import_row_missing_name_produces_error_message(self):
        upload = _make_excel_upload([
            ('full_name', 'national_id'),
            ('', '33333333333333'),  # missing name
        ])
        response = self.client.post(self.url, {'excel_file': upload})
        self.assertFalse(Student.objects.filter(
            national_id='33333333333333').exists())
        from django.contrib.messages import get_messages
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any('خطأ' in m for m in msgs))

    def test_import_template_download(self):
        response = self.client.get(
            reverse('admin_portal:student_import_template'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('attachment', response['Content-Disposition'])

    def test_teacher_cannot_import(self):
        self.client.logout()
        self.client.login(phone='01234567891', password='teacherpass123')
        upload = _make_excel_upload([
            ('full_name', 'national_id'),
            ('Blocked', '44444444444444'),
        ])
        self.client.post(self.url, {'excel_file': upload})
        self.assertFalse(Student.objects.filter(
            national_id='44444444444444').exists())
