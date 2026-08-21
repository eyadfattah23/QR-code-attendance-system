from django.test import TestCase, Client
from django.urls import reverse
from django.utils.timezone import localdate

from core.models import User, Student, Teacher, StudentTeacherLink, CoursePayment
import datetime

class DashboardUnpaidCountTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_user(
            phone='01000000000', password='pass', role=User.Role.ADMIN
        )
        cls.course1 = Teacher.objects.create(
            user=User.objects.create_user(phone='01100000001', password='pass', role=User.Role.TEACHER),
            full_name='Course A', is_course=True, is_active=True,
        )
        cls.course2 = Teacher.objects.create(
            user=User.objects.create_user(phone='01100000002', password='pass', role=User.Role.TEACHER),
            full_name='Course B', is_course=True, is_active=True,
        )
        cls.student1 = Student.objects.create(full_name='Student One', national_id='11111')
        cls.student2 = Student.objects.create(full_name='Student Two', national_id='22222')
        
        # Student 1 is in both courses
        StudentTeacherLink.objects.create(student=cls.student1, teacher=cls.course1)
        StudentTeacherLink.objects.create(student=cls.student1, teacher=cls.course2)
        
        # Student 2 is only in Course 1
        StudentTeacherLink.objects.create(student=cls.student2, teacher=cls.course1)

    def setUp(self):
        self.client = Client()
        self.client.login(phone='01000000000', password='pass')
        self.today = localdate()
        self.url = reverse('admin_portal:dashboard')

    def test_unpaid_count_with_no_payments(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context['this_month_unpaid_count'], 3) # 2 links for S1, 1 link for S2

    def test_unpaid_count_with_partial_and_paid(self):
        # S1 paid for Course 1
        CoursePayment.objects.create(
            student=self.student1, course=self.course1, year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.PAID
        )
        # S2 partially paid for Course 1
        CoursePayment.objects.create(
            student=self.student2, course=self.course1, year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.PARTIAL
        )
        
        response = self.client.get(self.url)
        # S1 still owes for Course 2, so count should be 1
        self.assertEqual(response.context['this_month_unpaid_count'], 1)

    def test_unpaid_count_with_not_paid_explicit_status(self):
        # S1 marked explicitly as NOT_PAID for Course 1
        CoursePayment.objects.create(
            student=self.student1, course=self.course1, year=self.today.year, month=self.today.month,
            status=CoursePayment.PaymentStatus.NOT_PAID
        )
        
        response = self.client.get(self.url)
        # Should still be 3 unpaid (it doesn't reduce the count)
        self.assertEqual(response.context['this_month_unpaid_count'], 3)

    def test_unpaid_count_ignores_past_months(self):
        if self.today.month == 1:
            past_month = 12
            past_year = self.today.year - 1
        else:
            past_month = self.today.month - 1
            past_year = self.today.year
            
        # S1 paid for Course 1 LAST month
        CoursePayment.objects.create(
            student=self.student1, course=self.course1, year=past_year, month=past_month,
            status=CoursePayment.PaymentStatus.PAID
        )
        
        response = self.client.get(self.url)
        # Should still be 3 unpaid this month
        self.assertEqual(response.context['this_month_unpaid_count'], 3)

    def test_unpaid_count_ignores_inactive_courses(self):
        self.course1.is_active = False
        self.course1.save()
        
        response = self.client.get(self.url)
        # Only Course 2 is active, which only has S1 enrolled (1 link)
        self.assertEqual(response.context['this_month_unpaid_count'], 1)

    def test_unpaid_count_ignores_non_courses(self):
        self.course1.is_course = False
        self.course1.save()
        
        response = self.client.get(self.url)
        # Only Course 2 is a course, which only has S1 enrolled (1 link)
        self.assertEqual(response.context['this_month_unpaid_count'], 1)
