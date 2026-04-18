"""
Management command to create an initial admin user.

Usage:
    python manage.py seed_admin
    python manage.py seed_admin --username=admin --password=mypassword
"""

from django.core.management.base import BaseCommand
from core.models import User


class Command(BaseCommand):
    help = 'Create an initial admin user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Username for the admin user (default: admin)'
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
        username = options['username']
        password = options['password']
        email = options['email']

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already exists.')
            )
            return

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created admin user:\n'
                f'  Username: {username}\n'
                f'  Email: {email}\n'
                f'  Password: {password}\n'
                f'\n'
                f'Please change the password after first login!'
            )
        )
