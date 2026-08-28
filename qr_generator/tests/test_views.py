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
        # Data stored in session, not URL params
        self.assertEqual(self.client.session['qr_student_ids'], [str(self.student1.id)])
        self.assertEqual(self.client.session['qr_cards_per_page'], '4')

    def test_post_multiple_students_appends_all_ids(self):
        self.client.login(phone='01800000000', password='adminpass')
        response = self.client.post(self.url, {
            'student_ids': [str(self.student1.id), str(self.student2.id)],
            'cards_per_page': '8',
        })
        self.assertEqual(response.status_code, 302)
        session_ids = self.client.session['qr_student_ids']
        self.assertIn(str(self.student1.id), session_ids)
        self.assertIn(str(self.student2.id), session_ids)


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


class QrCardsPhotoPrintRedirectTestCase(TestCase):
    """Tests that the 'print_photos' button redirects to the photo print page."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            phone='01800000010', password='adminpass',
            role=User.Role.ADMIN,
        )
        cls.teacher_user = User.objects.create_user(
            phone='01900000010', password='teacherpass',
            role=User.Role.TEACHER,
        )
        cls.teacher = Teacher.objects.create(user=cls.teacher_user, full_name='معلم')
        cls.student = Student.objects.create(
            full_name='طالب فوتو', national_id='30000000001234',
            student_code='PHO001',
        )
        cls.url = reverse('qr_generator:qr_cards_config')

    def setUp(self):
        self.client = Client()

    def test_print_photos_button_redirects_to_photo_print(self):
        self.client.login(phone='01800000010', password='adminpass')
        response = self.client.post(self.url, {
            'student_ids': [str(self.student.id)],
            'cards_per_page': '8',
            'print_photos': '1',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('qr_generator:qr_cards_photo_print'), response.url)
        self.assertEqual(self.client.session['qr_student_ids'], [str(self.student.id)])

    def test_default_submit_redirects_to_qr_print(self):
        self.client.login(phone='01800000010', password='adminpass')
        response = self.client.post(self.url, {
            'student_ids': [str(self.student.id)],
            'cards_per_page': '8',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('qr_generator:qr_cards_print'), response.url)


class QrCardsPhotoPrintTestCase(TestCase):
    """Tests for the photo cards print view."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            phone='01800000011', password='adminpass',
            role=User.Role.ADMIN,
        )
        cls.teacher_user = User.objects.create_user(
            phone='01900000011', password='teacherpass',
            role=User.Role.TEACHER,
        )
        cls.teacher = Teacher.objects.create(user=cls.teacher_user, full_name='معلم')
        cls.students = [
            Student.objects.create(
                full_name=f'طالب صور {i}', national_id=f'3100000000{i:04d}',
                student_code=f'PHT{i:03d}',
            )
            for i in range(1, 7)
        ]
        cls.url = reverse('qr_generator:qr_cards_photo_print')

    def setUp(self):
        self.client = Client()

    def _sid_params(self, students):
        return '&'.join(f'sid={s.id}' for s in students)

    def test_admin_can_access_photo_print(self):
        self.client.login(phone='01800000011', password='adminpass')
        url = f"{self.url}?{self._sid_params(self.students[:2])}&cpp=4"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_redirected(self):
        url = f"{self.url}?{self._sid_params(self.students[:1])}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_teacher_cannot_access_photo_print(self):
        self.client.login(phone='01900000011', password='teacherpass')
        url = f"{self.url}?{self._sid_params(self.students[:1])}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_student_names_in_photo_output(self):
        self.client.login(phone='01800000011', password='adminpass')
        url = f"{self.url}?{self._sid_params(self.students[:2])}&cpp=4"
        response = self.client.get(url)
        self.assertContains(response, 'طالب صور 1')
        self.assertContains(response, 'طالب صور 2')

    def test_no_photo_fallback_shown(self):
        """Students without images should show 'لا توجد صورة' placeholder."""
        self.client.login(phone='01800000011', password='adminpass')
        url = f"{self.url}?{self._sid_params(self.students[:1])}&cpp=1"
        response = self.client.get(url)
        self.assertContains(response, 'لا توجد صورة')

    def test_grid_layout_matches_qr_grid(self):
        """Photo print uses the same cols/rows as QR print for same cards_per_page."""
        self.client.login(phone='01800000011', password='adminpass')
        chosen = self.students[:4]
        sid_params = self._sid_params(chosen)

        qr_url = f"{reverse('qr_generator:qr_cards_print')}?{sid_params}&cpp=4"
        photo_url = f"{self.url}?{sid_params}&cpp=4"

        qr_resp = self.client.get(qr_url)
        photo_resp = self.client.get(photo_url)

        self.assertEqual(qr_resp.context['cols'], photo_resp.context['cols'])
        self.assertEqual(qr_resp.context['rows'], photo_resp.context['rows'])
        self.assertEqual(qr_resp.context['cards_per_page'], photo_resp.context['cards_per_page'])
        self.assertEqual(len(qr_resp.context['pages']), len(photo_resp.context['pages']))

    def test_ordering_matches_qr_ordering(self):
        """Photo print ordering must match QR print ordering."""
        self.client.login(phone='01800000011', password='adminpass')
        sid_params = self._sid_params(self.students)

        qr_url = f"{reverse('qr_generator:qr_cards_print')}?{sid_params}&cpp=6"
        photo_url = f"{self.url}?{sid_params}&cpp=6"

        qr_resp = self.client.get(qr_url)
        photo_resp = self.client.get(photo_url)

        qr_names = [c['student'].full_name for p in qr_resp.context['pages'] for c in p['cards']]
        photo_names = [c['student'].full_name for p in photo_resp.context['pages'] for c in p['cards']]

        self.assertEqual(qr_names, photo_names)

    def test_page_count_correct(self):
        self.client.login(phone='01800000011', password='adminpass')
        url = f"{self.url}?{self._sid_params(self.students)}&cpp=4"
        response = self.client.get(url)
        # 6 students / 4 per page = 2 pages
        self.assertEqual(len(response.context['pages']), 2)
        self.assertEqual(response.context['total_cards'], 6)

    def test_session_based_access(self):
        """Photo print should work with session data (not just URL params)."""
        self.client.login(phone='01800000011', password='adminpass')
        session = self.client.session
        session['qr_student_ids'] = [str(s.id) for s in self.students[:3]]
        session['qr_cards_per_page'] = '6'
        session.save()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_cards'], 3)


class TeacherQrCardsConfigTestCase(TestCase):
    """Tests for the teacher QR cards configuration view."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            phone='02800000000', password='adminpass',
            role=User.Role.ADMIN,
        )
        cls.teacher_user1 = User.objects.create_user(
            phone='02900000001', password='tpass',
            role=User.Role.TEACHER,
        )
        cls.teacher_user2 = User.objects.create_user(
            phone='02900000002', password='tpass',
            role=User.Role.TEACHER,
        )
        cls.teacher1 = Teacher.objects.create(
            user=cls.teacher_user1, full_name='أحمد خالد', subject='رياضيات',
        )
        cls.teacher2 = Teacher.objects.create(
            user=cls.teacher_user2, full_name='سارة يوسف', subject='علوم',
        )
        cls.url = reverse('qr_generator:teacher_qr_cards_config')

    def setUp(self):
        self.client = Client()

    # --- access control ---

    def test_admin_can_access_config_page(self):
        self.client.login(phone='02800000000', password='adminpass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_redirected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_teacher_cannot_access_config_page(self):
        self.client.login(phone='02900000001', password='tpass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    # --- GET rendering ---

    def test_config_page_lists_all_teachers(self):
        self.client.login(phone='02800000000', password='adminpass')
        response = self.client.get(self.url)
        self.assertContains(response, 'أحمد خالد')
        self.assertContains(response, 'سارة يوسف')

    def test_config_page_name_filter(self):
        self.client.login(phone='02800000000', password='adminpass')
        response = self.client.get(self.url, {'name': 'سارة'})
        self.assertNotContains(response, 'أحمد خالد')
        self.assertContains(response, 'سارة يوسف')

    def test_config_page_subject_filter(self):
        self.client.login(phone='02800000000', password='adminpass')
        response = self.client.get(self.url, {'subject': 'رياضيات'})
        self.assertContains(response, 'أحمد خالد')
        self.assertNotContains(response, 'سارة يوسف')

    def test_context_contains_subjects(self):
        self.client.login(phone='02800000000', password='adminpass')
        response = self.client.get(self.url)
        subjects = list(response.context['subjects'])
        self.assertIn('رياضيات', subjects)
        self.assertIn('علوم', subjects)

    # --- POST behaviour ---

    def test_post_without_teachers_shows_error(self):
        self.client.login(phone='02800000000', password='adminpass')
        response = self.client.post(self.url, {'cards_per_page': '8'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'يرجى اختيار معلم')

    def test_post_with_teachers_redirects_to_print(self):
        self.client.login(phone='02800000000', password='adminpass')
        response = self.client.post(self.url, {
            'teacher_ids': [str(self.teacher1.id)],
            'cards_per_page': '4',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('qr_generator:teacher_qr_cards_print'), response.url)
        # Data stored in session, not URL params
        self.assertEqual(self.client.session['qr_teacher_ids'], [str(self.teacher1.id)])
        self.assertEqual(self.client.session['qr_teacher_cards_per_page'], '4')

    def test_post_multiple_teachers_appends_all_ids(self):
        self.client.login(phone='02800000000', password='adminpass')
        response = self.client.post(self.url, {
            'teacher_ids': [str(self.teacher1.id), str(self.teacher2.id)],
            'cards_per_page': '8',
        })
        self.assertEqual(response.status_code, 302)
        session_ids = self.client.session['qr_teacher_ids']
        self.assertIn(str(self.teacher1.id), session_ids)
        self.assertIn(str(self.teacher2.id), session_ids)


class TeacherQrCardsPrintTestCase(TestCase):
    """Tests for the teacher QR cards print view."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            phone='02800000001', password='adminpass',
            role=User.Role.ADMIN,
        )
        cls.non_admin_user = User.objects.create_user(
            phone='02900000010', password='tpass',
            role=User.Role.TEACHER,
        )
        # Create 12 teachers for pagination tests
        cls.teachers = []
        for i in range(1, 13):
            u = User.objects.create_user(
                phone=f'0300000{i:04d}', password='tpass',
                role=User.Role.TEACHER,
            )
            cls.teachers.append(
                Teacher.objects.create(user=u, full_name=f'معلم {i}', subject='عربي')
            )
        cls.url = reverse('qr_generator:teacher_qr_cards_print')

    def setUp(self):
        self.client = Client()

    def _tid_params(self, teachers):
        return '&'.join(f'tid={t.id}' for t in teachers)

    # --- access control ---

    def test_admin_can_access_print_page(self):
        self.client.login(phone='02800000001', password='adminpass')
        url = f"{self.url}?{self._tid_params(self.teachers[:2])}&cpp=2"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_redirected(self):
        url = f"{self.url}?{self._tid_params(self.teachers[:1])}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_teacher_cannot_access_print_page(self):
        self.client.login(phone='02900000010', password='tpass')
        url = f"{self.url}?{self._tid_params(self.teachers[:1])}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    # --- QR images ---

    def test_response_contains_base64_qr_images(self):
        self.client.login(phone='02800000001', password='adminpass')
        url = f"{self.url}?{self._tid_params(self.teachers[:3])}&cpp=4"
        response = self.client.get(url)
        self.assertContains(response, 'data:image/png;base64,')

    def test_one_qr_per_teacher(self):
        self.client.login(phone='02800000001', password='adminpass')
        chosen = self.teachers[:5]
        url = f"{self.url}?{self._tid_params(chosen)}&cpp=6"
        response = self.client.get(url)
        content = response.content.decode()
        self.assertEqual(content.count('data:image/png;base64,'), 5)

    # --- teacher name in output ---

    def test_arabic_teacher_names_in_output(self):
        self.client.login(phone='02800000001', password='adminpass')
        url = f"{self.url}?{self._tid_params(self.teachers[:2])}&cpp=2"
        response = self.client.get(url)
        self.assertContains(response, 'معلم 1')
        self.assertContains(response, 'معلم 2')

    # --- pagination & context ---

    def test_twelve_teachers_fit_in_one_page_of_12(self):
        self.client.login(phone='02800000001', password='adminpass')
        url = f"{self.url}?{self._tid_params(self.teachers)}&cpp=12"
        response = self.client.get(url)
        self.assertEqual(len(response.context['pages']), 1)

    def test_twelve_teachers_split_into_two_pages_of_6(self):
        self.client.login(phone='02800000001', password='adminpass')
        url = f"{self.url}?{self._tid_params(self.teachers)}&cpp=6"
        response = self.client.get(url)
        self.assertEqual(len(response.context['pages']), 2)

    def test_context_total_cards_correct(self):
        self.client.login(phone='02800000001', password='adminpass')
        url = f"{self.url}?{self._tid_params(self.teachers[:7])}&cpp=4"
        response = self.client.get(url)
        self.assertEqual(response.context['total_cards'], 7)

    def test_invalid_cpp_clamped_to_valid_range(self):
        self.client.login(phone='02800000001', password='adminpass')
        url = f"{self.url}?{self._tid_params(self.teachers[:2])}&cpp=999"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(response.context['cards_per_page'], 12)

    def test_no_teachers_renders_empty_page(self):
        self.client.login(phone='02800000001', password='adminpass')
        response = self.client.get(f"{self.url}?cpp=4")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_cards'], 0)
        self.assertEqual(len(response.context['pages']), 0)
