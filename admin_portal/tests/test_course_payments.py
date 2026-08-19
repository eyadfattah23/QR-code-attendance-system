from django.test import TestCase, Client
from django.urls import reverse
from django.utils.timezone import localdate

from core.models import User, Student, Teacher, StudentTeacherLink, CoursePayment


class _CoursePaymentBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_user(
            phone='01000000000', password='pass', role=User.Role.ADMIN
        )
        cls.course = Teacher.objects.create(
            user=User.objects.create_user(
                phone='01100000001', password='pass', role=User.Role.TEACHER),
            full_name='Course A', is_course=True,
        )
        cls.regular_teacher = Teacher.objects.create(
            user=User.objects.create_user(
                phone='01100000002', password='pass', role=User.Role.TEACHER),
            full_name='Regular Teacher', is_course=False,
        )
        cls.student1 = Student.objects.create(
            full_name='Student One', national_id='11111111111111')
        cls.student2 = Student.objects.create(
            full_name='Student Two', national_id='22222222222222')
        StudentTeacherLink.objects.create(
            student=cls.student1, teacher=cls.course)
        StudentTeacherLink.objects.create(
            student=cls.student2, teacher=cls.course)

    def setUp(self):
        self.client = Client()
        self.client.login(phone='01000000000', password='pass')
        self.today = localdate()


class CourseRosterTestCase(_CoursePaymentBase):
    def test_roster_lists_enrolled_students(self):
        url = reverse('admin_portal:course_roster', args=[self.course.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Student One')
        self.assertContains(response, 'Student Two')

    def test_roster_404_for_non_course_teacher(self):
        url = reverse('admin_portal:course_roster',
                      args=[self.regular_teacher.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_roster_search_filters_students(self):
        url = reverse('admin_portal:course_roster', args=[self.course.pk])
        response = self.client.get(url, {'q': 'Student One'})
        self.assertContains(response, 'Student One')
        self.assertNotContains(response, 'Student Two')


class CoursePaymentCycleTestCase(_CoursePaymentBase):
    def test_cycle_creates_payment_and_advances_status(self):
        url = reverse('admin_portal:course_payment_cycle',
                      args=[self.course.pk, self.student1.pk])

        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        payment = CoursePayment.objects.get(
            student=self.student1, course=self.course,
            year=self.today.year, month=self.today.month,
        )
        self.assertEqual(payment.status, CoursePayment.PaymentStatus.PARTIAL)

        self.client.post(url)
        payment.refresh_from_db()
        self.assertEqual(payment.status, CoursePayment.PaymentStatus.PAID)

        # Cycles back to not_paid
        self.client.post(url)
        payment.refresh_from_db()
        self.assertEqual(payment.status, CoursePayment.PaymentStatus.NOT_PAID)

    def test_cycle_rejects_unenrolled_student(self):
        other_student = Student.objects.create(
            full_name='Not Enrolled', national_id='33333333333333')
        url = reverse('admin_portal:course_payment_cycle',
                      args=[self.course.pk, other_student.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_cycle_requires_post(self):
        url = reverse('admin_portal:course_payment_cycle',
                      args=[self.course.pk, self.student1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)


class CourseMarkAllPaidTestCase(_CoursePaymentBase):
    def test_mark_all_paid_creates_and_updates_payments(self):
        # student1 already partially paid; student2 has no payment row yet
        CoursePayment.objects.create(
            student=self.student1, course=self.course,
            year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.PARTIAL,
        )
        url = reverse('admin_portal:course_mark_all_paid',
                      args=[self.course.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        for student in (self.student1, self.student2):
            payment = CoursePayment.objects.get(
                student=student, course=self.course,
                year=self.today.year, month=self.today.month,
            )
            self.assertEqual(payment.status, CoursePayment.PaymentStatus.PAID)


class CoursePaymentHistoryTestCase(_CoursePaymentBase):
    def test_history_get_returns_12_months(self):
        url = reverse('admin_portal:course_payment_history',
                      args=[self.course.pk, self.student1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        for month in range(1, 13):
            self.assertContains(response, f'status_{month}')

    def test_history_post_saves_multiple_months(self):
        url = reverse('admin_portal:course_payment_history',
                      args=[self.course.pk, self.student1.pk])
        year = self.today.year
        data = {'year': year}
        for month in range(1, 13):
            data[f'status_{month}'] = CoursePayment.PaymentStatus.NOT_PAID
            data[f'amount_paid_{month}'] = ''
            data[f'note_{month}'] = ''
        data['status_1'] = CoursePayment.PaymentStatus.PAID
        data['amount_paid_1'] = '150.00'
        data['note_1'] = 'دفع نقدي'

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        payment = CoursePayment.objects.get(
            student=self.student1, course=self.course, year=year, month=1)
        self.assertEqual(payment.status, CoursePayment.PaymentStatus.PAID)
        self.assertEqual(str(payment.amount_paid), '150.00')
        self.assertEqual(payment.note, 'دفع نقدي')

    def test_history_rejects_unenrolled_student(self):
        other_student = Student.objects.create(
            full_name='Not Enrolled 2', national_id='44444444444444')
        url = reverse('admin_portal:course_payment_history',
                      args=[self.course.pk, other_student.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class StudentDetailCoursePaymentTestCase(_CoursePaymentBase):
    def test_student_detail_shows_course_payment_status(self):
        url = reverse('admin_portal:student_detail', args=[self.student1.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Course A')
        self.assertContains(response, 'لم يُدفع')


class PaymentsListTestCase(_CoursePaymentBase):
    def test_payments_list_shows_recorded_payments(self):
        CoursePayment.objects.create(
            student=self.student1, course=self.course,
            year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.PAID, amount_paid='100.00',
        )
        CoursePayment.objects.create(
            student=self.student2, course=self.course,
            year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.PARTIAL,
        )
        url = reverse('admin_portal:payments_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Student One')
        self.assertContains(response, 'Student Two')
        self.assertEqual(response.context['stats']['paid_count'], 1)
        self.assertEqual(response.context['stats']['partial_count'], 1)
        self.assertEqual(response.context['stats']['not_paid_count'], 0)

    def test_payments_list_filters_by_status(self):
        CoursePayment.objects.create(
            student=self.student1, course=self.course,
            year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.PAID,
        )
        CoursePayment.objects.create(
            student=self.student2, course=self.course,
            year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.NOT_PAID,
        )
        url = reverse('admin_portal:payments_list')
        response = self.client.get(
            url, {'status': CoursePayment.PaymentStatus.PAID})
        self.assertContains(response, 'Student One')
        self.assertNotContains(response, 'Student Two')

    def test_payments_list_filters_by_course(self):
        other_course = Teacher.objects.create(
            user=User.objects.create_user(
                phone='01100000003', password='pass', role=User.Role.TEACHER),
            full_name='Course B', is_course=True,
        )
        StudentTeacherLink.objects.create(
            student=self.student1, teacher=other_course)
        CoursePayment.objects.create(
            student=self.student1, course=self.course,
            year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.PAID,
        )
        CoursePayment.objects.create(
            student=self.student1, course=other_course,
            year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.NOT_PAID,
        )
        url = reverse('admin_portal:payments_list')
        response = self.client.get(url, {'course': str(self.course.pk)})
        self.assertEqual(len(response.context['page_obj']), 1)
        self.assertEqual(
            response.context['page_obj'][0].course_id, self.course.pk)

    def test_payments_list_search_by_student_name(self):
        CoursePayment.objects.create(
            student=self.student1, course=self.course,
            year=self.today.year, month=self.today.month,
        )
        CoursePayment.objects.create(
            student=self.student2, course=self.course,
            year=self.today.year, month=self.today.month,
        )
        url = reverse('admin_portal:payments_list')
        response = self.client.get(url, {'q': 'Student One'})
        self.assertContains(response, 'Student One')
        self.assertNotContains(response, 'Student Two')

    def test_payments_export_returns_xlsx(self):
        CoursePayment.objects.create(
            student=self.student1, course=self.course,
            year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.PAID, amount_paid='50.00',
        )
        url = reverse('admin_portal:payments_export')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('attachment', response['Content-Disposition'])

    def test_payments_export_respects_filters(self):
        CoursePayment.objects.create(
            student=self.student1, course=self.course,
            year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.PAID,
        )
        CoursePayment.objects.create(
            student=self.student2, course=self.course,
            year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.NOT_PAID,
        )
        import openpyxl
        from io import BytesIO
        url = reverse('admin_portal:payments_export')
        response = self.client.get(
            url, {'status': CoursePayment.PaymentStatus.PAID})
        wb = openpyxl.load_workbook(BytesIO(response.content))
        ws = wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 'Student One')
