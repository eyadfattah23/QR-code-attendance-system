from django.test import TestCase, Client
from django.urls import reverse
from django.utils.timezone import localdate
from core.models import User, Student, Teacher, StudentTeacherLink
from attendance.models import StudentAttendanceRecord

class TeacherScanTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher_user = User.objects.create_user(phone='01700000100', password='pass', role=User.Role.TEACHER)
        cls.teacher = Teacher.objects.create(user=cls.teacher_user, full_name='Scan Teacher')
        
        cls.student = Student.objects.create(full_name='Scan Student', national_id='10000000000001', student_code='SCAN01')
        StudentTeacherLink.objects.create(teacher=cls.teacher, student=cls.student, is_primary=True)

    def setUp(self):
        self.client = Client()
        self.client.login(phone='01700000100', password='pass')
        self.url = reverse('teacher_portal:scan')

    def test_scan_checkin_and_checkout(self):
        # 1. Check-in
        response = self.client.post(self.url, {'scanned_codes': self.student.id})
        self.assertEqual(response.status_code, 302)
        
        record = StudentAttendanceRecord.objects.get(student=self.student, date=localdate())
        self.assertIsNotNone(record.check_in_time)
        self.assertIsNone(record.check_out_time)
        
        # 2. Check-out
        response = self.client.post(self.url, {'scanned_codes': self.student.id})
        self.assertEqual(response.status_code, 302)
        
        record.refresh_from_db()
        self.assertIsNotNone(record.check_out_time)
        
        # 3. Third scan warns already checked out
        response = self.client.post(self.url, {'scanned_codes': self.student.id}, follow=True)
        self.assertContains(response, 'غادر مسبقاً')

