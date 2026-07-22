import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qr_attendance.settings")
django.setup()

from admin_portal.views import export_attendance_excel
from django.test import RequestFactory
import openpyxl

rf = RequestFactory()
request = rf.get('/?tab=teachers&date_from=2024-01-01&date_to=2024-01-31')
# Add a dummy user so admin_required doesn't fail
from core.models import User
request.user = User.objects.first()
if not request.user:
    request.user = User(role=User.Role.ADMIN, phone='01000000000')

# Actually, to bypass admin_required, we can just call the view. But admin_required decorator checks request.user.is_admin
if not getattr(request.user, 'is_admin', False):
    request.user.role = User.Role.ADMIN
try:
    response = export_attendance_excel(request)
    print(response.status_code)
except Exception as e:
    print(e)
