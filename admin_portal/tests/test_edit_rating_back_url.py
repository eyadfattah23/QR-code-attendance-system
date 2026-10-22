"""The edit-rating page must send the user back to the page they came from."""
import datetime

from django.test import TestCase, Client
from django.urls import reverse
from django.utils.timezone import make_aware

from attendance.models import StudentAttendanceRecord
from core.models import Student, StudentTeacherLink, Teacher, User


class EditRatingBackUrlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user(
            phone='02400000000', password='adminpass', role=User.Role.ADMIN)
        t_user = User.objects.create_user(
            phone='02411111111', password='tpass', role=User.Role.TEACHER)
        cls.teacher = Teacher.objects.create(user=t_user, full_name='معلم التقييم')
        cls.student = Student.objects.create(
            full_name='طالب الرجوع', national_id='72000000000001')
        StudentTeacherLink.objects.create(teacher=cls.teacher, student=cls.student)
        cls.record = StudentAttendanceRecord.objects.create(
            student=cls.student, date=datetime.date(2025, 9, 1),
            check_in_time=make_aware(datetime.datetime(2025, 9, 1, 8, 0)),
            original_teacher=cls.teacher, assigned_teacher=cls.teacher, rating=6,
        )
        cls.url = reverse('admin_portal:attendance_record_edit_rating',
                          args=[cls.record.pk])
        cls.teacher_dash = reverse('teacher_portal:dashboard')

    def setUp(self):
        self.client = Client()
        self.client.login(phone='02400000000', password='adminpass')

    def test_admin_from_teacher_portal_returns_there_after_save(self):
        back = self.teacher_dash + '?sort=name_asc'
        response = self.client.get(self.url, {'next': back})
        self.assertEqual(response.context['back_url'], back)
        response = self.client.post(self.url, {'rating': '9', 'next': back})
        self.assertRedirects(response, back, fetch_redirect_response=False)
        self.record.refresh_from_db()
        self.assertEqual(self.record.rating, 9)

    def test_referer_used_when_no_next(self):
        response = self.client.get(self.url, HTTP_REFERER='http://testserver' + self.teacher_dash)
        self.assertEqual(response.context['back_url'], 'http://testserver' + self.teacher_dash)

    def test_external_next_is_rejected(self):
        response = self.client.post(
            self.url, {'rating': '7', 'next': 'https://evil.example.com/'})
        self.assertRedirects(
            response, reverse('admin_portal:student_history', args=[self.student.pk]))

    def test_admin_default_is_student_history(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context['back_url'],
                         reverse('admin_portal:student_history', args=[self.student.pk]))

    def test_teacher_default_is_dashboard(self):
        self.client.logout()
        self.client.login(phone='02411111111', password='tpass')
        response = self.client.post(self.url, {'rating': '8'})
        self.assertRedirects(response, self.teacher_dash)

    def test_teacher_dashboard_link_carries_next(self):
        from django.utils.timezone import localdate, now
        today_rec = StudentAttendanceRecord.objects.create(
            student=self.student, date=localdate(), check_in_time=now(),
            original_teacher=self.teacher, assigned_teacher=self.teacher,
        )
        self.client.logout()
        self.client.login(phone='02411111111', password='tpass')
        response = self.client.get(self.teacher_dash)
        url = reverse('admin_portal:attendance_record_edit_rating', args=[today_rec.pk])
        self.assertContains(response, url + '?next=/portal/teacher/')
