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

    def test_scan_result_shows_student_image(self):
        import shutil
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings

        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        with override_settings(MEDIA_ROOT=media):
            gif = (b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
                   b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
                   b'\x00\x02\x02D\x01\x00;')
            self.student.image = SimpleUploadedFile('s.gif', gif, content_type='image/gif')
            self.student.save()

            response = self.client.post(
                self.url, {'scanned_codes': self.student.id}, follow=True)
            results = response.context['scan_results']
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['row_class'], 'success')
            self.assertEqual(results[0]['label'], 'Scan Student')
            self.assertEqual(results[0]['image_url'], self.student.image.url)
            self.assertContains(response, self.student.image.url)

    def test_scan_result_placeholder_without_image(self):
        response = self.client.post(
            self.url, {'scanned_codes': self.student.id}, follow=True)
        result = response.context['scan_results'][0]
        self.assertTrue(result['has_image'])
        self.assertIsNone(result['image_url'])
        self.assertContains(response, 'bi-person-fill')

    def test_scan_results_shown_only_once(self):
        self.client.post(self.url, {'scanned_codes': self.student.id})
        self.client.get(reverse('teacher_portal:dashboard'))
        response = self.client.get(reverse('teacher_portal:dashboard'))
        self.assertEqual(response.context['scan_results'], [])

    def test_unknown_code_result_has_no_image(self):
        response = self.client.post(
            self.url, {'scanned_codes': 'NOPE999'}, follow=True)
        result = response.context['scan_results'][0]
        self.assertEqual(result['row_class'], 'danger')
        self.assertFalse(result['has_image'])

