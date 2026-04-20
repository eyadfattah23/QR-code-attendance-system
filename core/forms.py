"""
Authentication forms for the QR Attendance System.

This module contains forms for user authentication including:
- LoginForm: User login with phone/password validation
"""

import re
from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError


class LoginForm(forms.Form):
    """
    Form for user login authentication using phone number.

    Attributes:
        phone: The user's phone number (11 digits starting with 0)
        password: The user's password
    """

    phone = forms.CharField(
        max_length=11,
        min_length=11,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'أدخل رقم الهاتف',
            'autofocus': True,
            'autocomplete': 'tel',
            'inputmode': 'numeric',
            'pattern': r'0\d{10}',
            'dir': 'ltr',
        }),
        error_messages={
            'required': 'رقم الهاتف مطلوب',
            'max_length': 'رقم الهاتف يجب أن يكون 11 رقم',
            'min_length': 'رقم الهاتف يجب أن يكون 11 رقم',
        }
    )

    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'أدخل كلمة المرور',
            'autocomplete': 'current-password',
        }),
        error_messages={
            'required': 'كلمة المرور مطلوبة',
        }
    )

    def __init__(self, request=None, *args, **kwargs):
        """
        Initialize the login form.

        Args:
            request: The HTTP request object for authentication context
        """
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean_phone(self):
        """
        Validate phone number format: 11 digits starting with 0.

        Returns:
            The cleaned phone number

        Raises:
            ValidationError: If phone format is invalid
        """
        phone = self.cleaned_data.get('phone', '').strip()

        if not re.match(r'^0\d{10}$', phone):
            raise ValidationError(
                'رقم الهاتف يجب أن يكون 11 رقم ويبدأ بصفر (مثال: 01234567890)',
                code='invalid_phone'
            )

        return phone

    def clean(self):
        """
        Validate credentials and authenticate the user.

        Returns:
            The cleaned form data

        Raises:
            ValidationError: If authentication fails
        """
        cleaned_data = super().clean()
        phone = cleaned_data.get('phone')
        password = cleaned_data.get('password')

        if phone and password:
            # First check if user exists and is inactive
            from core.models import User
            try:
                user = User.objects.get(phone=phone)
                if not user.is_active:
                    raise ValidationError(
                        'هذا الحساب معطل. يرجى التواصل مع المسؤول',
                        code='inactive'
                    )
            except User.DoesNotExist:
                pass

            # Authenticate using phone as username (since USERNAME_FIELD = 'phone')
            self.user_cache = authenticate(
                self.request,
                username=phone,  # Django uses 'username' param but checks USERNAME_FIELD
                password=password
            )

            if self.user_cache is None:
                raise ValidationError(
                    'رقم الهاتف أو كلمة المرور غير صحيحة',
                    code='invalid_login'
                )

        return cleaned_data

    def get_user(self):
        """
        Return the authenticated user.

        Returns:
            User: The authenticated user or None
        """
        return self.user_cache
