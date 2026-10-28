"""URLs called by ZKTeco fingerprint devices in ADMS mode.

The firmware hard-codes these paths, so they are mounted at /iclock/ on the
site root and have no trailing slash.
"""

from django.urls import path

from . import iclock

app_name = "iclock"

urlpatterns = [
    path("cdata", iclock.cdata, name="cdata"),
    path("getrequest", iclock.getrequest, name="getrequest"),
    path("devicecmd", iclock.devicecmd, name="devicecmd"),
    path("ping", iclock.ping, name="ping"),
]
