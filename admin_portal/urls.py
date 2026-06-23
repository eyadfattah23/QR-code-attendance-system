from django.urls import path
from . import views

app_name = 'admin_portal'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Student management
    path('students/', views.student_list, name='student_list'),
    path('students/create/', views.student_create, name='student_create'),
    # template must come before import/ to avoid prefix clash
    path('students/import/template/', views.student_import_template,
         name='student_import_template'),
    path('students/import/', views.student_import, name='student_import'),
    path('students/export/', views.student_export, name='student_export'),
    path('students/<uuid:pk>/history/',
         views.student_history, name='student_history'),
    path('students/<uuid:pk>/detail/', views.student_detail, name='student_detail'),
    path('students/<uuid:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<uuid:pk>/delete/',
         views.student_delete, name='student_delete'),

    # Attendance records
    path('attendance/', views.attendance_records, name='attendance_records'),
    path('attendance/export/', views.export_attendance_excel,
         name='attendance_export'),
    path('attendance/<uuid:pk>/edit-photo/',
         views.attendance_record_edit_photo, name='attendance_record_edit_photo'),
    path('attendance/<uuid:pk>/edit-rating/',
         views.attendance_record_edit_rating, name='attendance_record_edit_rating'),
    path('attendance/<uuid:pk>/teacher-edit/',
         views.teacher_attendance_record_edit, name='teacher_attendance_record_edit'),

    # Teacher management
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/create/', views.teacher_create, name='teacher_create'),
    path('teachers/import/template/', views.teacher_import_template,
         name='teacher_import_template'),
    path('teachers/import/', views.teacher_import, name='teacher_import'),
    path('teachers/<uuid:pk>/edit/', views.teacher_edit, name='teacher_edit'),
    path('teachers/<uuid:pk>/delete/',
         views.teacher_delete, name='teacher_delete'),
    path('teachers/<uuid:pk>/students/',
         views.teacher_students, name='teacher_students'),
    path('teachers/<uuid:pk>/mark-absent/',
         views.teacher_mark_absent, name='teacher_mark_absent'),
]
