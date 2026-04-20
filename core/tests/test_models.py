"""
Tests for User model and authentication-related model methods.

This module contains unit tests for:
- User model creation
- Role properties (is_admin, is_teacher)
- User string representation
- Phone number validation
"""

import pytest
from django.test import TestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from core.models import User, validate_phone_number


class UserModelTestCase(TestCase):
    """Test cases for the User model."""

    def test_create_admin_user(self):
        """Test creating a user with admin role."""
        user = User.objects.create_user(
            phone='01234567890',
            email='admin@test.com',
            password='testpass123',
            role=User.Role.ADMIN,
            first_name='Test',
            last_name='Admin'
        )
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_admin)
        self.assertFalse(user.is_teacher)

    def test_create_teacher_user(self):
        """Test creating a user with teacher role."""
        user = User.objects.create_user(
            phone='01234567891',
            email='teacher@test.com',
            password='testpass123',
            role=User.Role.TEACHER,
            first_name='Test',
            last_name='Teacher'
        )
        self.assertEqual(user.role, User.Role.TEACHER)
        self.assertTrue(user.is_teacher)
        self.assertFalse(user.is_admin)

    def test_default_role_is_teacher(self):
        """Test that default role is teacher."""
        user = User.objects.create_user(
            phone='01234567892',
            password='testpass123'
        )
        self.assertEqual(user.role, User.Role.TEACHER)

    def test_user_string_representation_with_full_name(self):
        """Test user string representation with full name."""
        user = User.objects.create_user(
            phone='01234567893',
            password='testpass123',
            first_name='John',
            last_name='Doe',
            role=User.Role.ADMIN
        )
        self.assertEqual(str(user), 'John Doe (admin)')

    def test_user_string_representation_without_full_name(self):
        """Test user string representation without full name (uses phone)."""
        user = User.objects.create_user(
            phone='01234567894',
            password='testpass123',
            role=User.Role.TEACHER
        )
        self.assertEqual(str(user), '01234567894 (teacher)')

    def test_unique_phone(self):
        """Test that phone must be unique."""
        User.objects.create_user(phone='01234567895', password='pass123')
        with self.assertRaises(IntegrityError):
            User.objects.create_user(phone='01234567895', password='pass456')

    def test_phone_format_valid(self):
        """Test valid phone number format (11 digits starting with 0)."""
        user = User.objects.create_user(
            phone='01234567896',
            password='testpass123'
        )
        self.assertEqual(user.phone, '01234567896')
        self.assertEqual(len(user.phone), 11)
        self.assertTrue(user.phone.startswith('0'))

    def test_is_admin_property(self):
        """Test is_admin property returns correct boolean."""
        admin = User.objects.create_user(
            phone='01234567897',
            password='pass',
            role=User.Role.ADMIN
        )
        teacher = User.objects.create_user(
            phone='01234567898',
            password='pass',
            role=User.Role.TEACHER
        )

        self.assertTrue(admin.is_admin)
        self.assertFalse(teacher.is_admin)

    def test_is_teacher_property(self):
        """Test is_teacher property returns correct boolean."""
        admin = User.objects.create_user(
            phone='01111111111',
            password='pass',
            role=User.Role.ADMIN
        )
        teacher = User.objects.create_user(
            phone='01111111112',
            password='pass',
            role=User.Role.TEACHER
        )

        self.assertFalse(admin.is_teacher)
        self.assertTrue(teacher.is_teacher)

    def test_get_full_name(self):
        """Test get_full_name method."""
        user = User.objects.create_user(
            phone='01111111113',
            password='pass',
            first_name='أحمد',
            last_name='محمد'
        )
        self.assertEqual(user.get_full_name(), 'أحمد محمد')

    def test_create_superuser(self):
        """Test creating a superuser."""
        superuser = User.objects.create_superuser(
            phone='01111111114',
            email='super@test.com',
            password='superpass123'
        )
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_staff)

    def test_username_field_is_phone(self):
        """Test that USERNAME_FIELD is set to phone."""
        self.assertEqual(User.USERNAME_FIELD, 'phone')


class PhoneValidationTestCase(TestCase):
    """Test cases for phone number validation."""

    def test_valid_phone_number(self):
        """Test that valid phone numbers pass validation."""
        valid_phones = ['01234567890', '01111111111', '01000000000']
        for phone in valid_phones:
            try:
                validate_phone_number(phone)
            except ValidationError:
                self.fail(f'Phone {phone} should be valid')

    def test_invalid_phone_too_short(self):
        """Test that short phone numbers fail validation."""
        with self.assertRaises(ValidationError):
            validate_phone_number('0123456789')  # 10 digits

    def test_invalid_phone_too_long(self):
        """Test that long phone numbers fail validation."""
        with self.assertRaises(ValidationError):
            validate_phone_number('012345678901')  # 12 digits

    def test_invalid_phone_not_starting_with_zero(self):
        """Test that phone not starting with 0 fails validation."""
        with self.assertRaises(ValidationError):
            validate_phone_number('11234567890')  # Starts with 1

    def test_invalid_phone_with_letters(self):
        """Test that phone with letters fails validation."""
        with self.assertRaises(ValidationError):
            validate_phone_number('0123456789a')

    def test_invalid_phone_with_spaces(self):
        """Test that phone with spaces fails validation."""
        with self.assertRaises(ValidationError):
            validate_phone_number('0123 456 789')


# Pytest-style tests
@pytest.mark.django_db
class TestUserModelPytest:
    """Pytest-style tests for User model."""

    def test_role_choices(self):
        """Test that role choices are defined correctly."""
        assert User.Role.ADMIN == 'admin'
        assert User.Role.TEACHER == 'teacher'

    def test_role_display_values(self):
        """Test role display values."""
        assert User.Role.ADMIN.label == 'Admin'
        assert User.Role.TEACHER.label == 'Teacher'

    def test_user_model_db_table(self):
        """Test that User model uses correct database table."""
        assert User._meta.db_table == 'users'

    def test_user_password_is_hashed(self):
        """Test that user password is hashed, not stored in plain text."""
        user = User.objects.create_user(
            phone='01222222222',
            password='plainpassword'
        )
        assert user.password != 'plainpassword'
        assert user.check_password('plainpassword')

    def test_phone_is_username_field(self):
        """Test that phone is used as the USERNAME_FIELD."""
        assert User.USERNAME_FIELD == 'phone'
