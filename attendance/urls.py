from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("", views.station_view, name="station"),
]
