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
]
