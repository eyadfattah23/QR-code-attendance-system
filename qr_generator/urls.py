from django.urls import path
from . import views

app_name = 'qr_generator'

urlpatterns = [
    path('', views.qr_cards_config, name='qr_cards_config'),
    path('print/', views.qr_cards_print, name='qr_cards_print'),
    path('photos/', views.qr_cards_photo_print, name='qr_cards_photo_print'),
    path('teachers/', views.teacher_qr_cards_config, name='teacher_qr_cards_config'),
    path('teachers/print/', views.teacher_qr_cards_print, name='teacher_qr_cards_print'),
]
