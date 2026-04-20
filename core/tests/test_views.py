"""
Tests for authentication views.

This module contains integration tests for authentication views including:
- Login view (GET/POST)
- Logout view
- Dashboard redirect view
- Access control decorators
"""

import pytest
from django.test import TestCase, Client
from django.urls import reverse

from core.models import User


class LoginViewTestCase(TestCase):
    """Test cases for the login view."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all test methods."""
        cls.admin_user = User.objects.create_user(
            phone='01234567890',
            email='admin@test.com',
            password='adminpass123',
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

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.login_url = reverse('login')
        self.dashboard_url = reverse('dashboard')

    # GET Request Tests
    def test_login_page_loads_successfully(self):
        """Test that login page returns 200."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)

    def test_login_page_uses_correct_template(self):
        """Test that login page uses auth/login.html template."""
        response = self.client.get(self.login_url)
        self.assertTemplateUsed(response, 'auth/login.html')

    def test_login_page_contains_form(self):
        """Test that login page contains login form."""
        response = self.client.get(self.login_url)
        self.assertIn('form', response.context)

    def test_login_page_has_csrf_token(self):
        """Test that login page has CSRF token."""
        response = self.client.get(self.login_url)
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_authenticated_user_redirected_from_login(self):
        """Test that authenticated user is redirected from login page."""
        self.client.login(phone='01234567890', password='adminpass123')
        response = self.client.get(self.login_url)
        self.assertRedirects(response, self.dashboard_url,
                             fetch_redirect_response=False)

    # POST Request Tests - Valid Credentials
    def test_successful_admin_login(self):
        """Test successful login with admin credentials."""
        response = self.client.post(self.login_url, {
            'phone': '01234567890',
            'password': 'adminpass123'
        })
        self.assertRedirects(response, self.dashboard_url,
                             fetch_redirect_response=False)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_successful_teacher_login(self):
        """Test successful login with teacher credentials."""
        response = self.client.post(self.login_url, {
            'phone': '01234567891',
            'password': 'teacherpass123'
        })
        self.assertRedirects(response, self.dashboard_url,
                             fetch_redirect_response=False)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_login_sets_session(self):
        """Test that login sets session correctly."""
        self.client.post(self.login_url, {
            'phone': '01234567890',
            'password': 'adminpass123'
        })
        # Session should have the user ID
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_with_next_parameter(self):
        """Test login redirects to 'next' URL when provided."""
        admin_dashboard = reverse('admin_portal:dashboard')
        response = self.client.post(
            f'{self.login_url}?next={admin_dashboard}',
            {'phone': '01234567890', 'password': 'adminpass123'}
        )
        self.assertRedirects(response, admin_dashboard)

    # POST Request Tests - Invalid Credentials
    def test_invalid_phone_login(self):
        """Test login with non-existent phone."""
        response = self.client.post(self.login_url, {
            'phone': '01999999999',
            'password': 'adminpass123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_invalid_password_login(self):
        """Test login with wrong password."""
        response = self.client.post(self.login_url, {
            'phone': '01234567890',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_empty_credentials_login(self):
        """Test login with empty credentials."""
        response = self.client.post(self.login_url, {
            'phone': '',
            'password': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_error_message_displayed(self):
        """Test that error message is displayed for invalid login."""
        response = self.client.post(self.login_url, {
            'phone': '01234567890',
            'password': 'wrongpassword'
        })
        self.assertContains(response, 'غير صحيحة')

    def test_invalid_phone_format_rejected(self):
        """Test login with invalid phone format."""
        response = self.client.post(self.login_url, {
            'phone': '1234567890',  # Missing leading 0
            'password': 'adminpass123'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class LogoutViewTestCase(TestCase):
    """Test cases for the logout view."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = User.objects.create_user(
            phone='01234567893',
            password='testpass123',
            role=User.Role.ADMIN
        )

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.logout_url = reverse('logout')
        self.login_url = reverse('login')

    def test_logout_redirects_to_login(self):
        """Test that logout redirects to login page."""
        self.client.login(phone='01234567893', password='testpass123')
        response = self.client.get(self.logout_url)
        self.assertRedirects(response, self.login_url)

    def test_logout_clears_session(self):
        """Test that logout clears user session."""
        self.client.login(phone='01234567893', password='testpass123')
        self.assertIn('_auth_user_id', self.client.session)

        self.client.get(self.logout_url)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_unauthenticated_user(self):
        """Test logout for already logged out user."""
        response = self.client.get(self.logout_url)
        self.assertRedirects(response, self.login_url)

    def test_logout_message_displayed(self):
        """Test that logout success message is displayed."""
        self.client.login(phone='01234567893', password='testpass123')
        response = self.client.get(self.logout_url, follow=True)
        self.assertContains(response, 'تم تسجيل الخروج بنجاح')


class DashboardRedirectViewTestCase(TestCase):
    """Test cases for the dashboard redirect view."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.admin_user = User.objects.create_user(
            phone='01234567894',
            password='adminpass123',
            role=User.Role.ADMIN
        )
        cls.teacher_user = User.objects.create_user(
            phone='01234567895',
            password='teacherpass123',
            role=User.Role.TEACHER
        )

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.dashboard_url = reverse('dashboard')

    def test_unauthenticated_user_redirected_to_login(self):
        """Test that unauthenticated user is redirected to login."""
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_admin_redirected_to_admin_dashboard(self):
        """Test that admin is redirected to admin portal."""
        self.client.login(phone='01234567894', password='adminpass123')
        response = self.client.get(self.dashboard_url)
        self.assertRedirects(response, reverse('admin_portal:dashboard'))

    def test_teacher_redirected_to_teacher_dashboard(self):
        """Test that teacher is redirected to teacher portal."""
        self.client.login(phone='01234567895', password='teacherpass123')
        response = self.client.get(self.dashboard_url)
        self.assertRedirects(response, reverse('teacher_portal:dashboard'))


class AccessControlTestCase(TestCase):
    """Test cases for access control decorators."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.admin_user = User.objects.create_user(
            phone='01234567896',
            password='adminpass123',
            role=User.Role.ADMIN
        )
        cls.teacher_user = User.objects.create_user(
            phone='01234567897',
            password='teacherpass123',
            role=User.Role.TEACHER
        )

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()

    def test_admin_can_access_admin_dashboard(self):
        """Test that admin can access admin portal."""
        self.client.login(phone='01234567896', password='adminpass123')
        response = self.client.get(reverse('admin_portal:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_teacher_cannot_access_admin_dashboard(self):
        """Test that teacher cannot access admin portal."""
        self.client.login(phone='01234567897', password='teacherpass123')
        response = self.client.get(reverse('admin_portal:dashboard'))
        # Should redirect with error message
        self.assertEqual(response.status_code, 302)

    def test_teacher_can_access_teacher_dashboard(self):
        """Test that teacher can access teacher portal."""
        self.client.login(phone='01234567897', password='teacherpass123')
        response = self.client.get(reverse('teacher_portal:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_teacher_dashboard(self):
        """Test that admin can access teacher portal (if allowed)."""
        self.client.login(phone='01234567896', password='adminpass123')
        response = self.client.get(reverse('teacher_portal:dashboard'))
        # Admin should be redirected since they're not a teacher
        self.assertEqual(response.status_code, 302)


# Pytest-style integration tests
@pytest.mark.django_db
class TestAuthenticationFlows:
    """Pytest-style integration tests for authentication flows."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return Client()

    @pytest.fixture
    def admin_user(self):
        """Create an admin user."""
        return User.objects.create_user(
            phone='01888888888',
            password='adminpass',
            role=User.Role.ADMIN
        )

    @pytest.fixture
    def teacher_user(self):
        """Create a teacher user."""
        return User.objects.create_user(
            phone='01888888889',
            password='teacherpass',
            role=User.Role.TEACHER
        )

    def test_full_login_logout_cycle(self, client, admin_user):
        """Test complete login-logout cycle."""
        # Login
        response = client.post(reverse('login'), {
            'phone': '01888888888',
            'password': 'adminpass'
        }, follow=True)
        assert response.wsgi_request.user.is_authenticated

        # Logout
        response = client.get(reverse('logout'), follow=True)
        assert not response.wsgi_request.user.is_authenticated

    def test_protected_page_requires_login(self, client):
        """Test that protected pages require login."""
        response = client.get(reverse('admin_portal:dashboard'))
        assert response.status_code == 302
        assert 'login' in response.url

    def test_login_preserves_next_url(self, client, admin_user):
        """Test that login preserves and redirects to 'next' URL."""
        target_url = reverse('admin_portal:dashboard')
        login_url = f"{reverse('login')}?next={target_url}"

        response = client.post(login_url, {
            'phone': '01888888888',
            'password': 'adminpass'
        })

        assert response.url == target_url
