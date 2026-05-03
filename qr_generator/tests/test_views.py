from django.test import TestCase, Client
from django.urls import reverse

from core.models import User, Student, Teacher


class QrCardsConfigTestCase(TestCase):
    """Tests for the QR cards configuration/selection view."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            phone='01800000000', password='adminpass',
            role=User.Role.ADMIN,
        )
        cls.teacher_user = User.objects.create_user(
            phone='01900000000', password='teacherpass',
            role=User.Role.TEACHER,
        )
        cls.teacher = Teacher.objects.create(user=cls.teacher_user, full_name='معلم تجريبي')
        cls.student1 = Student.objects.create(
            full_name='أحمد محمد', national_id='10000000000001',
            student_code='STU001', grade='الصف الأول',
        )
        cls.student2 = Student.objects.create(
            full_name='سارة علي', national_id='10000000000002',
            student_code='STU002', grade='الصف الثاني',
        )
        cls.url = reverse('qr_generator:qr_cards_config')

    def setUp(self):
        self.client = Client()

    # --- access control ---

    def test_admin_can_access_config_page(self):
        self.client.login(phone='01800000000', password='adminpass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_redirected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_teacher_cannot_access_config_page(self):
        self.client.login(phone='01900000000', password='teacherpass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    # --- GET rendering ---

    def test_config_page_lists_all_students(self):
        self.client.login(phone='01800000000', password='adminpass')
        response = self.client.get(self.url)
        self.assertContains(response, 'أحمد محمد')
        self.assertContains(response, 'سارة علي')

    def test_config_page_grade_filter_narrows_students(self):
        self.client.login(phone='01800000000', password='adminpass')
        response = self.client.get(self.url, {'grade': 'الصف الأول'})
        self.assertContains(response, 'أحمد محمد')
        self.assertNotContains(response, 'سارة علي')

    def test_config_page_name_filter(self):
        self.client.login(phone='01800000000', password='adminpass')
        response = self.client.get(self.url, {'name': 'سارة'})
        self.assertNotContains(response, 'أحمد محمد')
        self.assertContains(response, 'سارة علي')

    def test_context_contains_grades(self):
        self.client.login(phone='01800000000', password='adminpass')
        response = self.client.get(self.url)
        grades = list(response.context['grades'])
        self.assertIn('الصف الأول', grades)
        self.assertIn('الصف الثاني', grades)

    # --- POST behaviour ---

    def test_post_without_students_shows_error(self):
        self.client.login(phone='01800000000', password='adminpass')
        response = self.client.post(self.url, {'cards_per_page': '8'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'يرجى اختيار طالب')

    def test_post_with_students_redirects_to_print(self):
        self.client.login(phone='01800000000', password='adminpass')
        response = self.client.post(self.url, {
            'student_ids': [str(self.student1.id)],
            'cards_per_page': '4',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('qr_generator:qr_cards_print'), response.url)
        self.assertIn('sid=', response.url)
        self.assertIn('cpp=4', response.url)

    def test_post_multiple_students_appends_all_ids(self):
        self.client.login(phone='01800000000', password='adminpass')
        response = self.client.post(self.url, {
            'student_ids': [str(self.student1.id), str(self.student2.id)],
            'cards_per_page': '8',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(str(self.student1.id), response.url)
        self.assertIn(str(self.student2.id), response.url)


class QrCardsPrintTestCase(TestCase):
    """Tests for the QR cards print view."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            phone='01800000001', password='adminpass',
            role=User.Role.ADMIN,
        )
        cls.teacher_user = User.objects.create_user(
            phone='01900000001', password='teacherpass',
            role=User.Role.TEACHER,
        )
        cls.teacher = Teacher.objects.create(user=cls.teacher_user, full_name='معلم')
        cls.students = [
            Student.objects.create(
                full_name=f'طالب {i}', national_id=f'2000000000{i:04d}',
                student_code=f'STU{i:03d}',
            )
            for i in range(1, 13)
        ]
        cls.url = reverse('qr_generator:qr_cards_print')

    def setUp(self):
        self.client = Client()

    def _sid_params(self, students):
        return '&'.join(f'sid={s.id}' for s in students)

    # --- access control ---

    def test_admin_can_access_print_page(self):
        self.client.login(phone='01800000001', password='adminpass')
        url = f"{self.url}?{self._sid_params(self.students[:2])}&cpp=2"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_redirected(self):
        url = f"{self.url}?{self._sid_params(self.students[:1])}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_teacher_cannot_access_print_page(self):
        self.client.login(phone='01900000001', password='teacherpass')
        url = f"{self.url}?{self._sid_params(self.students[:1])}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    # --- QR images ---

    def test_response_contains_base64_qr_images(self):
        self.client.login(phone='01800000001', password='adminpass')
        url = f"{self.url}?{self._sid_params(self.students[:3])}&cpp=4"
        response = self.client.get(url)
        self.assertContains(response, 'data:image/png;base64,')

    def test_one_qr_per_student(self):
        self.client.login(phone='01800000001', password='adminpass')
        chosen = self.students[:5]
        url = f"{self.url}?{self._sid_params(chosen)}&cpp=6"
        response = self.client.get(url)
        content = response.content.decode()
        self.assertEqual(content.count('data:image/png;base64,'), 5)

    # --- student name in output ---

    def test_arabic_student_names_in_output(self):
        self.client.login(phone='01800000001', password='adminpass')
        url = f"{self.url}?{self._sid_params(self.students[:2])}&cpp=2"
        response = self.client.get(url)
        self.assertContains(response, 'طالب 1')
        self.assertContains(response, 'طالب 2')

    # --- pagination & context ---

    def test_twelve_students_fit_in_one_page_of_12(self):
        self.client.login(phone='01800000001', password='adminpass')
        url = f"{self.url}?{self._sid_params(self.students)}&cpp=12"
        response = self.client.get(url)
        self.assertEqual(len(response.context['pages']), 1)

    def test_twelve_students_split_into_two_pages_of_6(self):
        self.client.login(phone='01800000001', password='adminpass')
        url = f"{self.url}?{self._sid_params(self.students)}&cpp=6"
        response = self.client.get(url)
        self.assertEqual(len(response.context['pages']), 2)

    def test_context_total_cards_correct(self):
        self.client.login(phone='01800000001', password='adminpass')
        url = f"{self.url}?{self._sid_params(self.students[:7])}&cpp=4"
        response = self.client.get(url)
        self.assertEqual(response.context['total_cards'], 7)

    def test_invalid_cpp_clamped_to_valid_range(self):
        self.client.login(phone='01800000001', password='adminpass')
        url = f"{self.url}?{self._sid_params(self.students[:2])}&cpp=999"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(response.context['cards_per_page'], 12)

    def test_zero_cpp_clamped_to_one(self):
        self.client.login(phone='01800000001', password='adminpass')
        url = f"{self.url}?{self._sid_params(self.students[:2])}&cpp=0"
        response = self.client.get(url)
        self.assertEqual(response.context['cards_per_page'], 1)

    def test_no_students_renders_empty_page(self):
        self.client.login(phone='01800000001', password='adminpass')
        response = self.client.get(f"{self.url}?cpp=4")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_cards'], 0)
        self.assertEqual(len(response.context['pages']), 0)
