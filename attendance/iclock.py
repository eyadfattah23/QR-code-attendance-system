"""Endpoints for ZKTeco fingerprint devices in ADMS ("iclock" push) mode.

The device initiates every request:

* ``GET  /iclock/cdata?SN=..&options=all`` — handshake; we answer with upload options.
* ``POST /iclock/cdata?SN=..&table=ATTLOG`` — punches, one per line:
  ``<user id>\\t<YYYY-MM-DD HH:MM:SS>\\t<status>\\t<verify>\\t...``; we answer ``OK: <n>``.
* ``GET  /iclock/getrequest?SN=..`` — heartbeat asking for commands; we answer ``OK`` (none).
* ``POST /iclock/devicecmd?SN=..`` — command results; we answer ``OK``.

Anything other than an OK makes the device keep the data and send it again later.
"""

import logging
import re
from datetime import datetime, timedelta

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from core.models import Teacher

from .models import BiometricDevice, DevicePunch
from .services import record_teacher_scan

logger = logging.getLogger(__name__)

SERIAL_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
ATTLOG_LINE_RE = re.compile(
    r'^\s*(?P<pin>\S{1,20})\s+(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
    r'(?:\s+(?P<status>\d+))?(?:\s+(?P<verify>\d+))?'
)

# Punches outside this window mean the device clock is wrong; they are logged, not applied.
MAX_FUTURE_SKEW = timedelta(minutes=10)
MAX_PUNCH_AGE = timedelta(days=30)

# Handshake reply: upload punches only, in real time; poll for commands every 10 seconds.
HANDSHAKE_OPTIONS = (
    'ATTLOGStamp=None',
    'OPERLOGStamp=9999',
    'ATTPHOTOStamp=None',
    'ErrorDelay=30',
    'Delay=10',
    'TransTimes=00:00;14:05',
    'TransInterval=1',
    'TransFlag=TransData AttLog',
    'Realtime=1',
    'Encrypt=None',
    'ServerVer=2.4.1',
)


def _plain(body, status=200):
    return HttpResponse(body, content_type='text/plain', status=status)


def _client_ip(request):
    """Best-effort device IP for display; behind nginx REMOTE_ADDR is 127.0.0.1."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR') or None


def _approved_device(request):
    """Return ``(device, None)`` for an approved device, else ``(None, error_response)``.

    Unknown devices are registered as inactive so an admin can approve them.
    """
    serial = request.GET.get('SN', '').strip()
    if not SERIAL_RE.match(serial):
        return None, _plain('ERROR: missing or invalid SN', status=400)

    device, created = BiometricDevice.objects.get_or_create(serial_number=serial)
    if created:
        logger.warning(
            'New fingerprint device %s registered; approve it in Django admin '
            '(Biometric devices) to start recording punches.', serial)
    BiometricDevice.objects.filter(pk=device.pk).update(
        last_seen_at=timezone.now(), last_ip=_client_ip(request))

    if not device.is_active:
        return None, _plain('ERROR: device not approved', status=403)
    return device, None


def _apply_punch(punch):
    """Turn one stored punch into teacher attendance.

    Returns ``(result, teacher, attendance_record)`` for the punch log.
    """
    pin = punch.device_user_id
    teacher = None
    if pin.isdigit() and len(pin) <= 9:
        teacher = Teacher.objects.filter(device_user_id=int(pin)).first()
    if teacher is None:
        return DevicePunch.Rejection.UNKNOWN_USER, None, None
    if not teacher.is_active:
        return DevicePunch.Rejection.INACTIVE_TEACHER, teacher, None

    now = timezone.now()
    if not now - MAX_PUNCH_AGE <= punch.punch_time <= now + MAX_FUTURE_SKEW:
        return DevicePunch.Rejection.INVALID_TIME, teacher, None

    scan = record_teacher_scan(teacher, at=punch.punch_time)
    return scan.outcome, teacher, scan.record


def save_attlog(device, body):
    """Store and apply every punch in an ATTLOG upload.

    Returns how many lines were accepted (re-sent punches count; they are no-ops).
    """
    accepted = 0
    for line in body.splitlines():
        if not line.strip():
            continue
        match = ATTLOG_LINE_RE.match(line)
        try:
            naive_time = datetime.strptime(match['time'], '%Y-%m-%d %H:%M:%S')
        except (TypeError, ValueError):  # no regex match, or an impossible date
            logger.warning('Device %s sent an unreadable punch line: %r',
                           device.serial_number, line)
            continue
        accepted += 1

        with transaction.atomic():
            punch, created = DevicePunch.objects.get_or_create(
                device=device,
                device_user_id=match['pin'],
                punch_time=timezone.make_aware(naive_time),
                defaults={
                    'status': int(match['status']) if match['status'] else None,
                    'verify_type': int(match['verify']) if match['verify'] else None,
                },
            )
            if not created:
                continue
            try:
                with transaction.atomic():
                    punch.result, punch.teacher, punch.attendance_record = _apply_punch(punch)
            except Exception:
                # One bad punch must not block the device's upload queue; it stays in the log.
                logger.exception('Failed to apply punch %s from device %s',
                                 punch, device.serial_number)
                punch.result = DevicePunch.Rejection.ERROR
            punch.save(update_fields=['result', 'teacher', 'attendance_record'])

        logger.info('Device %s punch: user %s at %s -> %s', device.serial_number,
                    punch.device_user_id, punch.punch_time, punch.result)
    return accepted


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def cdata(request):
    """Handshake (GET) and data uploads (POST) from the device."""
    device, error = _approved_device(request)
    if error is not None:
        return error

    if request.method == 'GET':
        lines = (f'GET OPTION FROM: {device.serial_number}',) + HANDSHAKE_OPTIONS
        return _plain('\n'.join(lines) + '\n')

    if request.GET.get('table', '').upper() == 'ATTLOG':
        body = request.body.decode('utf-8', errors='replace')
        return _plain(f'OK: {save_attlog(device, body)}')

    # OPERLOG, options and other tables carry nothing we use; acknowledge so the device moves on.
    return _plain('OK')


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def getrequest(request):
    """Heartbeat: the device asks for pending commands; we never queue any."""
    _, error = _approved_device(request)
    return error or _plain('OK')


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def ping(request):
    """Backup heartbeat some firmware sends while busy uploading."""
    _, error = _approved_device(request)
    return error or _plain('OK')


@csrf_exempt
@require_POST
def devicecmd(request):
    """Command results; acknowledged only, since we never send commands."""
    _, error = _approved_device(request)
    return error or _plain('OK')
