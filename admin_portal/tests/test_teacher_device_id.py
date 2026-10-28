"""Tests for the fingerprint device ID (رقم جهاز البصمة) on the teacher form."""

from django.test import TestCase

from admin_portal.forms import TeacherForm
from core.models import Teacher, User


class TeacherDeviceIdFormTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.existing = Teacher.objects.create(
            user=User.objects.create_user(
                phone='01300000001', password='pass', role=User.Role.TEACHER),
            full_name='Existing Teacher',
            device_user_id=105,
        )

    def _data(self, **overrides):
        data = {
            'full_name': 'New Teacher',
            'phone': '01300000002',
            'password': 'pass12345',
            'is_active': 'on',
        }
        data.update(overrides)
        return data

    def test_create_saves_device_id(self):
        form = TeacherForm(data=self._data(device_user_id='210'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().device_user_id, 210)

    def test_device_id_is_optional(self):
        form = TeacherForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save().device_user_id)

    def test_duplicate_device_id_is_rejected(self):
        form = TeacherForm(data=self._data(device_user_id='105'))
        self.assertFalse(form.is_valid())
        self.assertIn('device_user_id', form.errors)

    def test_edit_keeps_own_device_id_and_can_clear_it(self):
        data = self._data(full_name='Existing Teacher', phone='01300000001', password='')
        form = TeacherForm(data={**data, 'device_user_id': '105'}, instance=self.existing)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        form = TeacherForm(data={**data, 'device_user_id': ''}, instance=self.existing)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.existing.refresh_from_db()
        self.assertIsNone(self.existing.device_user_id)

    def test_edit_form_shows_current_device_id(self):
        form = TeacherForm(instance=self.existing)
        self.assertEqual(form.fields['device_user_id'].initial, 105)
