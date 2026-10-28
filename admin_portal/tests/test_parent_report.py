"""Tests for the parent report: data assembly, access, preview and PDF."""
import datetime
import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils.timezone import make_aware
from PIL import Image

from admin_portal.parent_report import (
    build_parent_report, month_period, parse_period, rating_tier,
)
from attendance.models import StudentAttendanceRecord
from core.models import User, Student, Teacher, StudentTeacherLink

TMP_MEDIA = tempfile.mkdtemp()


def _jpeg(name='exam.jpg'):
    buf = io.BytesIO()
    Image.new('RGB', (40, 60), (240, 240, 240)).save(buf, 'JPEG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg')


class RatingTierAndPeriodTests(TestCase):
    def test_tier_boundaries(self):
        self.assertEqual([rating_tier(r) for r in (1, 5, 6, 7, 8, 10)],
                         ['low', 'low', 'mid', 'mid', 'high', 'high'])

    def test_period_defaults_to_current_month(self):
        today = datetime.date(2026, 3, 18)
        self.assertEqual(parse_period({}, today=today),
                         (datetime.date(2026, 3, 1), today))

    def test_period_swaps_reversed_range_and_ignores_garbage(self):
        today = datetime.date(2026, 3, 18)
        self.assertEqual(
            parse_period({'date_from': '2026-02-20', 'date_to': '2026-02-01'}, today=today),
            (datetime.date(2026, 2, 1), datetime.date(2026, 2, 20)))
        self.assertEqual(parse_period({'date_from': 'nope'}, today=today),
                         (datetime.date(2026, 3, 1), today))

    def test_period_is_capped_to_a_year(self):
        date_from, date_to = parse_period(
            {'date_from': '2020-01-01', 'date_to': '2026-03-18'})
        self.assertEqual(date_to, datetime.date(2026, 3, 18))
        self.assertEqual((date_to - date_from).days, 365)

    def test_month_period_caps_at_today(self):
        today = datetime.date(2026, 3, 18)
        self.assertEqual(month_period(datetime.date(2026, 2, 10), today=today),
                         (datetime.date(2026, 2, 1), datetime.date(2026, 2, 28)))
        self.assertEqual(month_period(datetime.date(2026, 3, 5), today=today),
                         (datetime.date(2026, 3, 1), today))


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class ParentReportTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            phone='02700000000', password='adminpass', role=User.Role.ADMIN)
        cls.supervisor = User.objects.create_user(
            phone='02711111111', password='suppass', role=User.Role.SUPERVISOR)
        t1_user = User.objects.create_user(
            phone='02722222222', password='tpass', role=User.Role.TEACHER)
        t2_user = User.objects.create_user(
            phone='02733333333', password='tpass', role=User.Role.TEACHER)
        cls.quran = Teacher.objects.create(
            user=t1_user, full_name='معلم القرآن', subject='القرآن الكريم')
        cls.fiqh = Teacher.objects.create(
            user=t2_user, full_name='معلم الفقه', subject='الفقه')
        cls.student = Student.objects.create(
            full_name='طالب التقرير', nickname='سامي', national_id='73000000000001',
            student_code='REP001', gender='M')
        cls.other = Student.objects.create(
            full_name='زميل الحلقة', national_id='73000000000002')
        for s in (cls.student, cls.other):
            StudentTeacherLink.objects.create(student=s, teacher=cls.quran,
                                              is_primary=True)
            StudentTeacherLink.objects.create(student=s, teacher=cls.fiqh)
        StudentTeacherLink.objects.update(
            created_at=make_aware(datetime.datetime(2026, 5, 3)))

        cls.d = [datetime.date(2026, 5, day) for day in (1, 4, 6, 8, 11)]
        # Before the student was linked or attended: never counted.
        cls._rec(cls.other, cls.d[0], cls.quran, 7)
        # Quran sessions on d1, d2, d3 (the classmate always attends).
        for day in cls.d[1:4]:
            cls._rec(cls.other, day, cls.quran, 7)
        cls.low = cls._rec(cls.student, cls.d[1], cls.quran, 4, 'شغب أثناء الحلقة',
                           photo=True)
        cls.high = cls._rec(cls.student, cls.d[3], cls.quran, 9, 'حفظ ممتاز',
                            photo=True)
        # Fiqh: one session on d2.
        cls._rec(cls.other, cls.d[2], cls.fiqh, 6)
        cls.mid = cls._rec(cls.student, cls.d[2], cls.fiqh, 6, 'أداء جيد')
        # d[4] has no records at all: not a session.
        # Previous period (same length, right before May 4) average: 5.
        cls._rec(cls.student, datetime.date(2026, 4, 30), cls.fiqh, 5)

        cls.date_from, cls.date_to = datetime.date(2026, 5, 4), datetime.date(2026, 5, 12)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    @staticmethod
    def _rec(student, day, teacher, rating, note='', photo=False):
        rec = StudentAttendanceRecord.objects.create(
            student=student, date=day, original_teacher=teacher,
            assigned_teacher=teacher, rating=rating, teacher_note=note,
            check_in_time=make_aware(datetime.datetime.combine(day, datetime.time(16, 0))),
        )
        if photo:
            rec.test_photo = _jpeg()
            rec.save()
        return rec

    def report(self):
        return build_parent_report(self.student, self.date_from, self.date_to)


class BuildParentReportTests(ParentReportTestBase):
    def test_absences_inferred_only_from_held_sessions(self):
        subjects = {s['title']: s for s in self.report()['subjects']}
        quran = subjects['القرآن الكريم']
        self.assertEqual((quran['held'], quran['attended'], quran['absent']), (3, 2, 1))
        absent_days = [s['date'] for s in quran['sessions'] if not s['record']]
        self.assertEqual(absent_days, [self.d[2]])
        fiqh = subjects['الفقه']
        self.assertEqual((fiqh['held'], fiqh['attended']), (1, 1))

    def test_sessions_before_enrolment_are_not_counted(self):
        report = build_parent_report(self.student, self.d[0], self.date_to)
        quran = next(s for s in report['subjects'] if s['title'] == 'القرآن الكريم')
        self.assertNotIn(self.d[0], [s['date'] for s in quran['sessions']])

    def test_primary_subject_listed_first(self):
        self.assertEqual(self.report()['subjects'][0]['title'], 'القرآن الكريم')

    def test_stats_and_previous_period_delta(self):
        stats = self.report()['stats']
        self.assertEqual(stats['avg'], '6.3')
        self.assertEqual(stats['prev_avg'], '5')
        self.assertEqual((stats['delta'], stats['delta_sign']), ('1.3', 1))
        self.assertEqual((stats['held'], stats['attended'], stats['rate']), (4, 3, 75))
        self.assertEqual((stats['low'], stats['mid'], stats['high']), (1, 1, 1))

    def test_notes_grouped_by_tier(self):
        report = self.report()
        self.assertEqual(report['low_days'], [self.low])
        self.assertEqual(report['high_note_rows'], [[self.high, None]])
        self.assertEqual(report['mid_notes'], [self.mid])

    def test_low_rating_days_without_notes_are_still_listed(self):
        self.low.teacher_note = ''
        self.low.save()
        report = self.report()
        self.assertEqual([r.pk for r in report['low_days']], [self.low.pk])
        self.assertEqual(report['low_days'][0].note, '')

    def test_exam_photos_low_rating_first(self):
        report = self.report()
        self.assertEqual([r.pk for r in report['exams']], [self.low.pk, self.high.pk])
        self.assertEqual([row['cols'] for row in report['exam_rows']], [2, 3])

    def test_summary_mentions_attendance_and_low_days(self):
        summary = ' '.join(self.report()['summary'])
        self.assertIn('حضر سامي 3 من أصل 4 حصص', summary)
        self.assertIn('يوم واحد بتقييم منخفض', summary)

    def test_chart_points_run_right_to_left(self):
        points = self.report()['chart']['points']
        self.assertEqual(len(points), 3)
        self.assertGreater(points[0]['x'], points[-1]['x'])

    def test_empty_period(self):
        report = build_parent_report(
            self.student, datetime.date(2026, 1, 1), datetime.date(2026, 1, 31))
        self.assertIsNone(report['chart'])
        self.assertIsNone(report['stats']['avg'])
        self.assertEqual(report['exam_rows'], [])


class ParentReportViewTests(ParentReportTestBase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('admin_portal:student_parent_report', args=[self.student.pk])
        self.pdf_url = reverse('admin_portal:student_parent_report_pdf', args=[self.student.pk])
        self.params = {'date_from': '2026-05-04', 'date_to': '2026-05-12'}

    def test_admin_sees_preview(self):
        self.client.login(phone='02700000000', password='adminpass')
        response = self.client.get(self.url, self.params)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'طالب التقرير')
        self.assertContains(response, 'شغب أثناء الحلقة')
        self.assertContains(response, self.pdf_url + '?date_from=2026-05-04&amp;date_to=2026-05-12')

    def test_supervisor_sees_preview_and_returns_to_records(self):
        self.client.login(phone='02711111111', password='suppass')
        response = self.client.get(self.url, self.params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['back_url'],
                         reverse('admin_portal:attendance_records'))

    def test_teacher_is_refused(self):
        self.client.login(phone='02722222222', password='tpass')
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.get(self.pdf_url).status_code, 302)

    def test_external_next_is_ignored(self):
        self.client.login(phone='02700000000', password='adminpass')
        response = self.client.get(self.url, {**self.params, 'next': 'https://evil.example/'})
        self.assertEqual(response.context['back_url'],
                         reverse('admin_portal:student_detail', args=[self.student.pk]))
        response = self.client.get(self.url, {**self.params, 'next': '/portal/admin/attendance/?tab=students'})
        self.assertEqual(response.context['back_url'], '/portal/admin/attendance/?tab=students')

    def test_pdf_download(self):
        self.client.login(phone='02711111111', password='suppass')
        response = self.client.get(self.pdf_url, self.params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_student_detail_offers_report_dialog(self):
        self.client.login(phone='02700000000', password='adminpass')
        response = self.client.get(
            reverse('admin_portal:student_detail', args=[self.student.pk]))
        self.assertContains(response, 'id="parentReportModal"')
        self.assertContains(response, self.url)


class AttendanceRecordsReportEntryTests(ParentReportTestBase):
    def setUp(self):
        self.client = Client()
        self.client.login(phone='02711111111', password='suppass')
        self.records_url = reverse('admin_portal:attendance_records')

    def test_rows_use_the_filtered_range(self):
        response = self.client.get(self.records_url, {
            'tab': 'students', 'student': 'REP001',
            'date_from': '2026-05-04', 'date_to': '2026-05-12'})
        self.assertEqual(response.context['report_date_from'], '2026-05-04')
        self.assertEqual(response.context['report_student_id'], str(self.student.pk))
        rec = response.context['student_page'][0]
        self.assertIn('date_from=2026-05-04', rec.report_query)
        self.assertIn('date_to=2026-05-12', rec.report_query)
        # Supervisors (read-only) still get the report link but not delete.
        self.assertContains(response, 'تقرير ولي الأمر لهذا الطالب')
        self.assertNotContains(response, 'حذف السجل')

    def test_rows_fall_back_to_the_record_month(self):
        response = self.client.get(self.records_url, {'tab': 'students', 'student': 'REP001'})
        rec = response.context['student_page'][0]
        self.assertIn('date_from=2026-05-01', rec.report_query)
        self.assertIn('date_to=2026-05-31', rec.report_query)

    def test_ambiguous_search_preselects_nobody(self):
        response = self.client.get(self.records_url, {'tab': 'students', 'student': '7300000000'})
        self.assertEqual(response.context['report_student_id'], '')

    def test_picker_options_load_on_demand(self):
        url = reverse('admin_portal:parent_report_student_options')
        response = self.client.get(url, {'q': 'REP001'})
        self.assertContains(response, 'طالب التقرير')
        self.assertContains(response, ' selected')
        self.assertNotContains(response, 'زميل الحلقة')
        response = self.client.get(url, {'q': 'لا أحد'})
        self.assertContains(response, 'لا يوجد طالب مطابق')

    def test_picker_options_require_admin_or_supervisor(self):
        self.client.login(phone='02722222222', password='tpass')
        url = reverse('admin_portal:parent_report_student_options')
        self.assertEqual(self.client.get(url).status_code, 302)
