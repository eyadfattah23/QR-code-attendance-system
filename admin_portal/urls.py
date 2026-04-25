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
    path('students/<uuid:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<uuid:pk>/delete/',
         views.student_delete, name='student_delete'),

    # Teacher management
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/create/', views.teacher_create, name='teacher_create'),
    path('teachers/<uuid:pk>/edit/', views.teacher_edit, name='teacher_edit'),
    path('teachers/<uuid:pk>/delete/',
         views.teacher_delete, name='teacher_delete'),
]
