from django.urls import path
from . import views

app_name = 'assistant_portal'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('teacher/<uuid:pk>/select/', views.select_teacher, name='select_teacher'),
    path('deselect/', views.deselect_teacher, name='deselect_teacher'),
]
