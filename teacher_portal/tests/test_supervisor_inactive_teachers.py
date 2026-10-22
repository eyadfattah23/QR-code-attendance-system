"""Deactivated (soft-deleted) teachers must not appear in, or be usable from,
the supervisor portal."""
from django.test import TestCase, Client
from django.urls import reverse

from core.models import Teacher, User


class SupervisorHidesInactiveTeachersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user(
            phone='02300000000', password='suppass', role=User.Role.SUPERVISOR)
        active_user = User.objects.create_user(
            phone='02311111111', password='tpass', role=User.Role.TEACHER)
        inactive_user = User.objects.create_user(
            phone='02322222222', password='tpass', role=User.Role.TEACHER)
        cls.active = Teacher.objects.create(
            user=active_user, full_name='معلم نشط', subject='مادة نشطة')
        cls.inactive = Teacher.objects.create(
            user=inactive_user, full_name='معلم محذوف', subject='مادة محذوفة',
            is_active=False)

    def setUp(self):
        self.client = Client()
        self.client.login(phone='02300000000', password='suppass')

    def test_dashboard_lists_only_active_teachers(self):
        response = self.client.get(reverse('supervisor_portal:dashboard'))
        teachers = [card['teacher'] for card in response.context['teacher_cards']]
        self.assertIn(self.active, teachers)
        self.assertNotIn(self.inactive, teachers)
        self.assertNotContains(response, 'معلم محذوف')

    def test_subject_filter_excludes_inactive_subjects(self):
        response = self.client.get(reverse('supervisor_portal:dashboard'))
        subjects = list(response.context['subjects'])
        self.assertIn('مادة نشطة', subjects)
        self.assertNotIn('مادة محذوفة', subjects)

    def test_cannot_select_inactive_teacher(self):
        response = self.client.post(
            reverse('supervisor_portal:select_teacher', args=[self.inactive.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('supervisor_teacher_id', self.client.session)

    def test_session_cleared_when_selected_teacher_is_deactivated(self):
        self.client.post(
            reverse('supervisor_portal:select_teacher', args=[self.active.pk]))
        self.assertEqual(self.client.get(reverse('teacher_portal:dashboard')).status_code, 200)

        Teacher.objects.filter(pk=self.active.pk).update(is_active=False)
        response = self.client.get(reverse('teacher_portal:dashboard'))
        self.assertRedirects(response, reverse('supervisor_portal:dashboard'))
        self.assertNotIn('supervisor_teacher_id', self.client.session)
