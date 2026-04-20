"""
Management command to create an initial admin user.

Usage:
    python manage.py seed_admin
    python manage.py seed_admin --phone=01234567890 --password=mypassword
"""

from django.core.management.base import BaseCommand
from core.models import User


class Command(BaseCommand):
    help = 'Create an initial admin user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phone',
            type=str,
            default='01000000000',
            help='Phone number for the admin user (default: 01000000000)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='admin123',
            help='Password for the admin user (default: admin123)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@example.com',
            help='Email for the admin user (default: admin@example.com)'
        )

    def handle(self, *args, **options):
        phone = options['phone']
        password = options['password']
        email = options['email']

        if User.objects.filter(phone=phone).exists():
            self.stdout.write(
                self.style.WARNING(
                    f'User with phone "{phone}" already exists.')
            )
            return

        user = User.objects.create_user(
            phone=phone,
            email=email,
            password=password,
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created admin user:\n'
                f'  Phone: {phone}\n'
                f'  Email: {email}\n'
                f'  Password: {password}\n'
                f'\n'
                f'Please change the password after first login!'
            )
        )
