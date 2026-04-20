"""
Tests for authentication forms.

This module contains unit tests for the LoginForm including:
- Form validation
- User authentication via phone number
- Error handling
"""

import pytest
from django.test import TestCase, RequestFactory

from core.forms import LoginForm
from core.models import User


class LoginFormTestCase(TestCase):
    """Test cases for the LoginForm."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all test methods."""
        cls.admin_user = User.objects.create_user(
            phone='01234567890',
            email='admin@test.com',
            password='testpass123',
            role=User.Role.ADMIN,
            first_name='Test',
            last_name='Admin'
        )
        cls.teacher_user = User.objects.create_user(
            phone='01234567891',
            email='teacher@test.com',
            password='teacherpass123',
            role=User.Role.TEACHER,
            first_name='Test',
            last_name='Teacher'
        )
        cls.inactive_user = User.objects.create_user(
            phone='01234567892',
            email='inactive@test.com',
            password='inactivepass123',
            role=User.Role.TEACHER,
            is_active=False
        )

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_form_has_required_fields(self):
        """Test that form has phone and password fields."""
        form = LoginForm()
        self.assertIn('phone', form.fields)
        self.assertIn('password', form.fields)

    def test_form_phone_required(self):
        """Test that phone field is required."""
        form = LoginForm(data={'phone': '', 'password': 'test'})
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

    def test_form_password_required(self):
        """Test that password field is required."""
        form = LoginForm(data={'phone': '01234567890', 'password': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_valid_admin_credentials(self):
        """Test login with valid admin credentials."""
        request = self.factory.post('/login/')
        form = LoginForm(request=request, data={
            'phone': '01234567890',
            'password': 'testpass123'
        })
        self.assertTrue(form.is_valid())
        user = form.get_user()
        self.assertEqual(user, self.admin_user)
        self.assertTrue(user.is_admin)

    def test_valid_teacher_credentials(self):
        """Test login with valid teacher credentials."""
        request = self.factory.post('/login/')
        form = LoginForm(request=request, data={
            'phone': '01234567891',
            'password': 'teacherpass123'
        })
        self.assertTrue(form.is_valid())
        user = form.get_user()
        self.assertEqual(user, self.teacher_user)
        self.assertTrue(user.is_teacher)

    def test_invalid_phone(self):
        """Test login with non-existent phone."""
        request = self.factory.post('/login/')
        form = LoginForm(request=request, data={
            'phone': '01999999999',
            'password': 'testpass123'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('رقم الهاتف أو كلمة المرور غير صحيحة', str(form.errors))

    def test_invalid_password(self):
        """Test login with wrong password."""
        request = self.factory.post('/login/')
        form = LoginForm(request=request, data={
            'phone': '01234567890',
            'password': 'wrongpassword'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('رقم الهاتف أو كلمة المرور غير صحيحة', str(form.errors))

    def test_inactive_user_login(self):
        """Test login attempt with inactive user."""
        request = self.factory.post('/login/')
        form = LoginForm(request=request, data={
            'phone': '01234567892',
            'password': 'inactivepass123'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('هذا الحساب معطل', str(form.errors))

    def test_get_user_returns_none_when_invalid(self):
        """Test that get_user returns None for invalid form."""
        form = LoginForm(data={'phone': '', 'password': ''})
        form.is_valid()
        self.assertIsNone(form.get_user())

    def test_phone_format_validation_too_short(self):
        """Test phone validation rejects numbers that are too short."""
        form = LoginForm(data={'phone': '0123456789', 'password': 'test'})
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

    def test_phone_format_validation_too_long(self):
        """Test phone validation rejects numbers that are too long."""
        form = LoginForm(data={'phone': '012345678901', 'password': 'test'})
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

    def test_phone_format_validation_not_starting_with_zero(self):
        """Test phone validation rejects numbers not starting with 0."""
        form = LoginForm(data={'phone': '11234567890', 'password': 'test'})
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

    def test_form_widgets_have_correct_classes(self):
        """Test that form widgets have Bootstrap CSS classes."""
        form = LoginForm()
        self.assertIn('form-control',
                      form.fields['phone'].widget.attrs.get('class', ''))
        self.assertIn('form-control',
                      form.fields['password'].widget.attrs.get('class', ''))

    def test_phone_field_has_tel_input(self):
        """Test that phone field has proper attributes for numeric input."""
        form = LoginForm()
        attrs = form.fields['phone'].widget.attrs
        self.assertEqual(attrs.get('inputmode'), 'numeric')
        self.assertEqual(attrs.get('autocomplete'), 'tel')


# Pytest-style tests for additional coverage
@pytest.mark.django_db
class TestLoginFormPytest:
    """Pytest-style tests for LoginForm."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(
            phone='01555555555',
            password='pytestpass123',
            role=User.Role.ADMIN
        )

    @pytest.fixture
    def request_factory(self):
        """Create a request factory."""
        return RequestFactory()

    def test_successful_authentication(self, user, request_factory):
        """Test successful authentication returns user."""
        request = request_factory.post('/login/')
        form = LoginForm(request=request, data={
            'phone': '01555555555',
            'password': 'pytestpass123'
        })
        assert form.is_valid()
        assert form.get_user() == user

    def test_empty_form_is_invalid(self, request_factory):
        """Test that empty form is not valid."""
        request = request_factory.post('/login/')
        form = LoginForm(request=request, data={})
        assert not form.is_valid()
        assert 'phone' in form.errors
        assert 'password' in form.errors

    def test_empty_form_is_invalid(self, request_factory):
        """Test that empty form is not valid."""
        request = request_factory.post('/login/')
        form = LoginForm(request=request, data={})
        assert not form.is_valid()
        assert 'username' in form.errors
        assert 'password' in form.errors
