from django.urls import path
from . import views

app_name = 'teacher_portal'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('scan/', views.teacher_scan, name='scan'),
]
