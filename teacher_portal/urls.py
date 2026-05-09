from django.urls import path
from . import views

app_name = 'teacher_portal'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('scan/', views.teacher_scan, name='scan'),
    path('students/<uuid:pk>/history/', views.student_history, name='student_history'),
    path('records/<uuid:pk>/note/', views.edit_record_note, name='edit_record_note'),
    path('records/<uuid:pk>/photo/', views.upload_photo, name='upload_photo'),
    path('export/', views.export_attendance, name='export_attendance'),
]
