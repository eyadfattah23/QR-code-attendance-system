"""
Tests for the ZKTeco fingerprint device integration.

This module contains tests for:
- record_teacher_scan, the check-in/out rules shared with the scan station
- The ADMS (iclock) endpoints the device pushes punches to
"""

from datetime import timedelta
from unittest import mock

from django.test import TestCase, Client
from django.urls import reverse
from django.utils.timezone import localtime

from core.models import User, Teacher
from attendance.models import (
    BiometricDevice,
    DevicePunch,
    TeacherAttendanceRecord,
    TeacherScanOutcome,
)
from attendance.services import record_teacher_scan

SERIAL = 'CQZ7232460123'


def _yesterday_at(hour, minute=0):
    """A fixed local time yesterday, so tests never straddle midnight."""
    return (localtime() - timedelta(days=1)).replace(
        hour=hour, minute=minute, second=0, microsecond=0)


def _make_teacher(phone, name, **extra):
    user = User.objects.create_user(phone=phone, password='pass', role=User.Role.TEACHER)
    return Teacher.objects.create(user=user, full_name=name, **extra)


class RecordTeacherScanTestCase(TestCase):
    """The shared first-scan-in / next-scan-out rules."""

    @classmethod
    def setUpTestData(cls):
        cls.teacher = _make_teacher('01200000001', 'Scan Teacher')

    def test_first_scan_checks_in_at_given_time(self):
        at = _yesterday_at(8)
        scan = record_teacher_scan(self.teacher, at=at)
        self.assertEqual(scan.outcome, TeacherScanOutcome.CHECKED_IN)
        self.assertEqual(scan.record.date, at.date())
        self.assertEqual(scan.record.check_in_time, at)
        self.assertIsNone(scan.record.check_out_time)

    def test_scan_within_five_minutes_is_ignored(self):
        record_teacher_scan(self.teacher, at=_yesterday_at(8))
        scan = record_teacher_scan(self.teacher, at=_yesterday_at(8, 4))
        self.assertEqual(scan.outcome, TeacherScanOutcome.TOO_EARLY)
        scan.record.refresh_from_db()
        self.assertIsNone(scan.record.check_out_time)

    def test_second_scan_checks_out(self):
        record_teacher_scan(self.teacher, at=_yesterday_at(8))
        scan = record_teacher_scan(self.teacher, at=_yesterday_at(14))
        self.assertEqual(scan.outcome, TeacherScanOutcome.CHECKED_OUT)
        scan.record.refresh_from_db()
        self.assertEqual(scan.record.check_out_time, _yesterday_at(14))

    def test_third_scan_reports_already_checked_out(self):
        record_teacher_scan(self.teacher, at=_yesterday_at(8))
        record_teacher_scan(self.teacher, at=_yesterday_at(14))
        scan = record_teacher_scan(self.teacher, at=_yesterday_at(16))
        self.assertEqual(scan.outcome, TeacherScanOutcome.ALREADY_CHECKED_OUT)
        scan.record.refresh_from_db()
        self.assertEqual(scan.record.check_out_time, _yesterday_at(14))
        self.assertEqual(TeacherAttendanceRecord.objects.count(), 1)

    def test_scan_before_check_in_is_rejected(self):
        record_teacher_scan(self.teacher, at=_yesterday_at(9))
        scan = record_teacher_scan(self.teacher, at=_yesterday_at(8))
        self.assertEqual(scan.outcome, TeacherScanOutcome.BEFORE_CHECK_IN)
        scan.record.refresh_from_db()
        self.assertIsNone(scan.record.check_out_time)

    def test_excused_absence_is_left_untouched(self):
        TeacherAttendanceRecord.objects.create(
            teacher=self.teacher,
            date=_yesterday_at(8).date(),
            record_type=TeacherAttendanceRecord.RecordType.EXCUSED_ABSENCE,
        )
        scan = record_teacher_scan(self.teacher, at=_yesterday_at(8))
        self.assertEqual(scan.outcome, TeacherScanOutcome.EXCUSED_ABSENCE)
        scan.record.refresh_from_db()
        self.assertIsNone(scan.record.check_in_time)

    def test_defaults_to_now_and_records_who_scanned(self):
        admin = User.objects.create_user(
            phone='01200000009', password='pass', role=User.Role.ADMIN)
        scan = record_teacher_scan(self.teacher, recorded_by=admin)
        self.assertEqual(scan.record.date, localtime().date())
        self.assertEqual(scan.record.recorded_by, admin)


class IclockEndpointTestCase(TestCase):
    """The ADMS push endpoints the fingerprint device calls."""

    @classmethod
    def setUpTestData(cls):
        cls.device = BiometricDevice.objects.create(serial_number=SERIAL, is_active=True)
        cls.teacher = _make_teacher('01200000002', 'Device Teacher', device_user_id=105)

    def setUp(self):
        # The device never sends a CSRF token, so test with CSRF checks on.
        self.client = Client(enforce_csrf_checks=True)
        self.cdata_url = reverse('iclock:cdata')

    def _upload(self, *lines, serial=SERIAL):
        return self.client.post(
            f'{self.cdata_url}?SN={serial}&table=ATTLOG&Stamp=9999',
            data='\n'.join(lines) + '\n',
            content_type='text/plain',
        )

    @staticmethod
    def _line(user_id, at, status=0, verify=1):
        return f"{user_id}\t{at.strftime('%Y-%m-%d %H:%M:%S')}\t{status}\t{verify}\t0\t0\t0\t0\t0\t0"

    def test_handshake_returns_options(self):
        response = self.client.get(f'{self.cdata_url}?SN={SERIAL}&options=all&pushver=2.4.1')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/plain'))
        body = response.content.decode()
        self.assertTrue(body.startswith(f'GET OPTION FROM: {SERIAL}\n'))
        self.assertIn('Realtime=1', body)
        self.assertIn('TransFlag=TransData AttLog', body)

    def test_request_without_serial_is_rejected(self):
        response = self.client.get(self.cdata_url)
        self.assertEqual(response.status_code, 400)

    def test_unknown_device_is_registered_inactive_and_refused(self):
        response = self.client.get(f'{self.cdata_url}?SN=NEWDEVICE01&options=all')
        self.assertEqual(response.status_code, 403)
        device = BiometricDevice.objects.get(serial_number='NEWDEVICE01')
        self.assertFalse(device.is_active)
        self.assertIsNotNone(device.last_seen_at)
        self.assertEqual(device.last_ip, '127.0.0.1')

    def test_unapproved_device_punches_are_not_stored(self):
        BiometricDevice.objects.create(serial_number='PENDING01')
        response = self._upload(self._line(105, _yesterday_at(8)), serial='PENDING01')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(DevicePunch.objects.exists())
        self.assertFalse(TeacherAttendanceRecord.objects.exists())

    def test_heartbeat_updates_last_seen(self):
        response = self.client.get(reverse('iclock:getrequest') + f'?SN={SERIAL}')
        self.assertEqual(response.content, b'OK')
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_seen_at)

    def test_ping_and_devicecmd_answer_ok(self):
        self.assertEqual(
            self.client.get(reverse('iclock:ping') + f'?SN={SERIAL}').content, b'OK')
        response = self.client.post(
            reverse('iclock:devicecmd') + f'?SN={SERIAL}',
            data='ID=1&Return=0&CMD=INFO', content_type='text/plain')
        self.assertEqual(response.content, b'OK')

    def test_other_tables_are_acknowledged(self):
        response = self.client.post(
            f'{self.cdata_url}?SN={SERIAL}&table=OPERLOG&Stamp=9999',
            data='OPLOG 4\t0\t2026-10-27 08:00:00\t0\t0\t0\t0\n', content_type='text/plain')
        self.assertEqual(response.content, b'OK')
        self.assertFalse(DevicePunch.objects.exists())

    def test_check_in_and_check_out_punches(self):
        response = self._upload(
            self._line(105, _yesterday_at(8)),
            self._line(105, _yesterday_at(14, 30), status=1),
        )
        self.assertEqual(response.content, b'OK: 2')

        record = TeacherAttendanceRecord.objects.get(teacher=self.teacher)
        self.assertEqual(record.date, _yesterday_at(8).date())
        self.assertEqual(record.check_in_time, _yesterday_at(8))
        self.assertEqual(record.check_out_time, _yesterday_at(14, 30))
        self.assertIsNone(record.recorded_by)

        results = list(DevicePunch.objects.order_by('punch_time').values_list('result', flat=True))
        self.assertEqual(results, [TeacherScanOutcome.CHECKED_IN, TeacherScanOutcome.CHECKED_OUT])
        punch = DevicePunch.objects.order_by('punch_time').first()
        self.assertEqual(punch.teacher, self.teacher)
        self.assertEqual(punch.attendance_record, record)
        self.assertEqual(punch.verify_type, 1)

    def test_upload_sent_as_form_content_type(self):
        """Some firmware labels the raw ATTLOG body as form data."""
        response = self.client.post(
            f'{self.cdata_url}?SN={SERIAL}&table=ATTLOG&Stamp=9999',
            data=self._line(105, _yesterday_at(8)),
            content_type='application/x-www-form-urlencoded',
        )
        self.assertEqual(response.content, b'OK: 1')
        self.assertTrue(TeacherAttendanceRecord.objects.filter(teacher=self.teacher).exists())

    def test_punches_in_separate_uploads(self):
        self._upload(self._line(105, _yesterday_at(8)))
        self._upload(self._line(105, _yesterday_at(14)))
        record = TeacherAttendanceRecord.objects.get(teacher=self.teacher)
        self.assertEqual(record.check_out_time, _yesterday_at(14))

    def test_resent_batch_is_a_no_op(self):
        lines = (self._line(105, _yesterday_at(8)), self._line(105, _yesterday_at(14)))
        self._upload(*lines)
        response = self._upload(*lines)
        self.assertEqual(response.content, b'OK: 2')
        self.assertEqual(DevicePunch.objects.count(), 2)
        record = TeacherAttendanceRecord.objects.get(teacher=self.teacher)
        self.assertEqual(record.check_in_time, _yesterday_at(8))
        self.assertEqual(record.check_out_time, _yesterday_at(14))

    def test_repeat_punch_within_five_minutes_does_not_check_out(self):
        self._upload(self._line(105, _yesterday_at(8)), self._line(105, _yesterday_at(8, 1)))
        record = TeacherAttendanceRecord.objects.get(teacher=self.teacher)
        self.assertIsNone(record.check_out_time)
        self.assertEqual(
            DevicePunch.objects.get(punch_time=_yesterday_at(8, 1)).result,
            TeacherScanOutcome.TOO_EARLY)

    def test_leading_zeros_in_user_id_still_match(self):
        self._upload(self._line('0105', _yesterday_at(8)))
        self.assertTrue(TeacherAttendanceRecord.objects.filter(teacher=self.teacher).exists())

    def test_unknown_user_is_logged_only(self):
        response = self._upload(self._line(999, _yesterday_at(8)))
        self.assertEqual(response.content, b'OK: 1')
        punch = DevicePunch.objects.get()
        self.assertEqual(punch.result, DevicePunch.Rejection.UNKNOWN_USER)
        self.assertIsNone(punch.teacher)
        self.assertFalse(TeacherAttendanceRecord.objects.exists())

    def test_inactive_teacher_is_logged_only(self):
        _make_teacher('01200000003', 'Former Teacher', device_user_id=106, is_active=False)
        self._upload(self._line(106, _yesterday_at(8)))
        self.assertEqual(DevicePunch.objects.get().result, DevicePunch.Rejection.INACTIVE_TEACHER)
        self.assertFalse(TeacherAttendanceRecord.objects.exists())

    def test_punch_with_wrong_device_clock_is_logged_only(self):
        far_past = localtime() - timedelta(days=400)
        far_future = localtime() + timedelta(days=2)
        self._upload(self._line(105, far_past), self._line(105, far_future))
        self.assertEqual(
            set(DevicePunch.objects.values_list('result', flat=True)),
            {DevicePunch.Rejection.INVALID_TIME})
        self.assertFalse(TeacherAttendanceRecord.objects.exists())

    def test_excused_absence_day_ignores_punches(self):
        TeacherAttendanceRecord.objects.create(
            teacher=self.teacher,
            date=_yesterday_at(8).date(),
            record_type=TeacherAttendanceRecord.RecordType.EXCUSED_ABSENCE,
        )
        self._upload(self._line(105, _yesterday_at(8)))
        self.assertEqual(DevicePunch.objects.get().result, TeacherScanOutcome.EXCUSED_ABSENCE)
        record = TeacherAttendanceRecord.objects.get(teacher=self.teacher)
        self.assertIsNone(record.check_in_time)

    def test_unreadable_lines_are_skipped(self):
        response = self._upload(
            'garbage',
            '105\t2026-02-30 08:00:00\t0\t1',
            self._line(105, _yesterday_at(8)),
        )
        self.assertEqual(response.content, b'OK: 1')
        self.assertEqual(DevicePunch.objects.count(), 1)

    def test_failing_punch_does_not_block_the_upload(self):
        with mock.patch('attendance.iclock.record_teacher_scan', side_effect=RuntimeError):
            response = self._upload(self._line(105, _yesterday_at(8)))
        self.assertEqual(response.content, b'OK: 1')
        self.assertEqual(DevicePunch.objects.get().result, DevicePunch.Rejection.ERROR)
