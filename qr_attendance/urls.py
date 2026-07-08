"""
URL configuration for qr_attendance project.
"""
import mimetypes
import os

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404


@login_required
def serve_media(request, path):
    """Serve files from MEDIA_ROOT. Requires authentication."""
    file_path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, path))
    # Prevent path traversal outside MEDIA_ROOT
    if not file_path.startswith(str(settings.MEDIA_ROOT)):
        raise Http404
    if not os.path.isfile(file_path):
        raise Http404
    content_type, _ = mimetypes.guess_type(file_path)
    return FileResponse(open(file_path, 'rb'), content_type=content_type or 'application/octet-stream')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('scan/', include('attendance.urls')),
    path('portal/admin/', include('admin_portal.urls')),
    path('portal/teacher/', include('teacher_portal.urls')),
    path('qr-cards/', include('qr_generator.urls')),
    re_path(r'^media/(?P<path>.+)$', serve_media),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
