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
    path('students/<uuid:pk>/detail/',
         views.student_detail, name='student_detail'),
    path('students/<uuid:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<uuid:pk>/delete/',
         views.student_delete, name='student_delete'),
    path('students/bulk-delete/',
         views.student_bulk_delete, name='student_bulk_delete'),

    # Attendance records
    path('attendance/', views.attendance_records, name='attendance_records'),
    path('attendance/export/', views.export_attendance_excel,
         name='attendance_export'),
    path('attendance/<uuid:pk>/edit-photo/',
         views.attendance_record_edit_photo, name='attendance_record_edit_photo'),
    path('attendance/<uuid:pk>/edit-rating/',
         views.attendance_record_edit_rating, name='attendance_record_edit_rating'),
    path('attendance/<uuid:pk>/edit-note/',
         views.attendance_record_edit_note, name='attendance_record_edit_note'),
    path('attendance/<uuid:pk>/teacher-edit/',
         views.teacher_attendance_record_edit, name='teacher_attendance_record_edit'),
    path('attendance/<uuid:pk>/delete/',
         views.student_attendance_record_delete, name='student_attendance_record_delete'),
    path('attendance/<uuid:pk>/teacher-delete/',
         views.teacher_attendance_record_delete, name='teacher_attendance_record_delete'),
    path('attendance/teacher-add-excused-absence/',
         views.teacher_add_excused_absence, name='teacher_add_excused_absence'),

    # Teacher management
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/create/', views.teacher_create, name='teacher_create'),
    path('teachers/import/template/', views.teacher_import_template,
         name='teacher_import_template'),
    path('teachers/import/', views.teacher_import, name='teacher_import'),
    path('teachers/export/', views.teacher_export, name='teacher_export'),
    path('teachers/<uuid:pk>/edit/', views.teacher_edit, name='teacher_edit'),
    path('teachers/<uuid:pk>/delete/',
         views.teacher_delete, name='teacher_delete'),
    path('teachers/<uuid:pk>/students/',
         views.teacher_students, name='teacher_students'),
    path('teachers/<uuid:pk>/students/export/',
         views.teacher_students_export, name='teacher_students_export'),
    path('teachers/<uuid:pk>/mark-absent/',
         views.teacher_mark_absent, name='teacher_mark_absent'),

    # Course payments
    path('courses/<uuid:pk>/roster/', views.course_roster, name='course_roster'),
    path('courses/<uuid:pk>/roster/mark-all-paid/',
         views.course_mark_all_paid, name='course_mark_all_paid'),
    path('courses/<uuid:pk>/roster/students/<uuid:student_pk>/cycle/',
         views.course_payment_cycle, name='course_payment_cycle'),
    path('courses/<uuid:pk>/roster/students/<uuid:student_pk>/history/',
         views.course_payment_history, name='course_payment_history'),
    path('payments/', views.payments_list, name='payments_list'),
    path('payments/export/', views.payments_export, name='payments_export'),

    # Supervisor management
    path('supervisors/', views.supervisor_list, name='supervisor_list'),
    path('supervisors/create/', views.supervisor_create, name='supervisor_create'),
    path('supervisors/<int:pk>/edit/',
         views.supervisor_edit, name='supervisor_edit'),
    path('supervisors/<int:pk>/delete/',
         views.supervisor_delete, name='supervisor_delete'),

    # Assistant management
    path('assistants/', views.assistant_list, name='assistant_list'),
    path('assistants/create/', views.assistant_create, name='assistant_create'),
    path('assistants/<int:pk>/edit/',
         views.assistant_edit, name='assistant_edit'),
    path('assistants/<int:pk>/delete/',
         views.assistant_delete, name='assistant_delete'),
    path('assistants/<int:pk>/links/',
         views.assistant_links, name='assistant_links'),

    # Audit log
    path('audit-log/', views.audit_log, name='audit_log'),
]
