from django.test import TestCase, Client
from django.urls import reverse
from core.models import User, Teacher, AssistantTeacherLink

class AssistantPortalTestCase(TestCase):
    """Tests for the assistant portal views and access control."""

    @classmethod
    def setUpTestData(cls):
        # Create an assistant user
        cls.assistant_user = User.objects.create_user(
            phone='01099990001', password='testpass123',
            role=User.Role.ASSISTANT,
            first_name='Musaed', last_name='Al-Awwal'
        )

        # Create a teacher
        cls.teacher_user = User.objects.create_user(
            phone='01099990002', password='teacherpass123',
            role=User.Role.TEACHER,
        )
        cls.teacher = Teacher.objects.create(
            user=cls.teacher_user, full_name='Teacher 1'
        )
        
        # Create a second teacher not linked
        cls.teacher2_user = User.objects.create_user(
            phone='01099990003', password='teacherpass123',
            role=User.Role.TEACHER,
        )
        cls.teacher2 = Teacher.objects.create(
            user=cls.teacher2_user, full_name='Teacher 2'
        )

        # Link assistant to first teacher
        cls.link = AssistantTeacherLink.objects.create(
            user=cls.assistant_user, teacher=cls.teacher
        )

        # Create a regular user for access control tests
        cls.regular_user = User.objects.create_user(
            phone='01099990004', password='testpass123',
            role=User.Role.TEACHER,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(phone='01099990001', password='testpass123')

    def test_dashboard_access(self):
        """Assistant can access dashboard."""
        url = reverse('assistant_portal:dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_only_linked_teachers(self):
        """Dashboard only lists teachers the assistant is linked to."""
        url = reverse('assistant_portal:dashboard')
        response = self.client.get(url)
        teachers = [card['teacher'] for card in response.context['teacher_cards']]
        self.assertIn(self.teacher, teachers)
        self.assertNotIn(self.teacher2, teachers)

    def test_non_assistant_cannot_access_dashboard(self):
        """Non-assistants are redirected."""
        self.client.login(phone='01099990004', password='testpass123')
        url = reverse('assistant_portal:dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

    def test_select_teacher_success(self):
        """Assistant can select a linked teacher."""
        url = reverse('assistant_portal:select_teacher', args=[self.teacher.pk])
        response = self.client.post(url)
        
        # Should redirect to teacher portal
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('teacher_portal:dashboard'))
        
        # Session should have the teacher ID
        self.assertEqual(
            self.client.session.get('assistant_teacher_id'),
            str(self.teacher.pk)
        )

    def test_select_teacher_forbidden(self):
        """Assistant cannot select an unlinked teacher."""
        url = reverse('assistant_portal:select_teacher', args=[self.teacher2.pk])
        response = self.client.post(url)
        
        # Should redirect back to assistant dashboard with error
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('assistant_portal:dashboard'))
        
        # Session should NOT have the teacher ID
        self.assertNotIn('assistant_teacher_id', self.client.session)

    def test_deselect_teacher(self):
        """Deselecting clears the session."""
        # First select
        self.client.post(reverse('assistant_portal:select_teacher', args=[self.teacher.pk]))
        self.assertIn('assistant_teacher_id', self.client.session)
        
        # Then deselect
        response = self.client.post(reverse('assistant_portal:deselect_teacher'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('assistant_portal:dashboard'))
        self.assertNotIn('assistant_teacher_id', self.client.session)
