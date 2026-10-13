"""Tests for supervisor read-only access to attendance records, the
specific-dates filter, and Excel export completeness."""
import datetime
import io

import openpyxl
from django.test import TestCase, Client
from django.urls import reverse
from django.utils.timezone import make_aware

from core.models import User, Student, Teacher
from attendance.models import StudentAttendanceRecord, TeacherAttendanceRecord


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            phone='02100000000', password='adminpass', role=User.Role.ADMIN)
        cls.supervisor = User.objects.create_user(
            phone='02111111111', password='suppass', role=User.Role.SUPERVISOR)
        t_user = User.objects.create_user(
            phone='02122222222', password='tpass', role=User.Role.TEACHER)
        cls.teacher = Teacher.objects.create(
            user=t_user, full_name='معلم أصلي')
        sub_user = User.objects.create_user(
            phone='02133333333', password='tpass', role=User.Role.TEACHER)
        cls.sub = Teacher.objects.create(user=sub_user, full_name='معلم بديل')
        cls.student = Student.objects.create(
            full_name='طالب التواريخ', national_id='60000000000001',
            student_code='DTS001', grade='الصف الأول')

        cls.days = [datetime.date(2025, 7, d) for d in (1, 3, 5, 7)]
        cls.student_recs = []
        for d in cls.days:
            cls.student_recs.append(StudentAttendanceRecord.objects.create(
                student=cls.student, date=d,
                check_in_time=make_aware(
                    datetime.datetime.combine(d, datetime.time(8, 0))),
                check_out_time=make_aware(
                    datetime.datetime.combine(d, datetime.time(10, 30))),
                original_teacher=cls.teacher, assigned_teacher=cls.sub,
                rating=8, teacher_note='ملاحظة', substitute_note='غياب',
            ))
            TeacherAttendanceRecord.objects.create(
                teacher=cls.teacher, date=d,
                check_in_time=make_aware(
                    datetime.datetime.combine(d, datetime.time(7, 45))),
            )
        cls.url = reverse('admin_portal:attendance_records')
        cls.export_url = reverse('admin_portal:attendance_export')

    def setUp(self):
        self.client = Client()

    def _rows(self, response):
        ws = openpyxl.load_workbook(io.BytesIO(response.content)).active
        return list(ws.iter_rows(values_only=True))


class SupervisorReadOnlyAttendanceTests(_Base):

    def setUp(self):
        super().setUp()
        self.client.login(phone='02111111111', password='suppass')

    def test_supervisor_can_view_students_tab_with_teacher_filter(self):
        r = self.client.get(self.url, {'teacher': str(self.sub.id)})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context['read_only'])
        self.assertEqual(r.context['student_total'], 4)

    def test_supervisor_sees_no_edit_or_delete_controls(self):
        r = self.client.get(self.url)
        for rec in self.student_recs:
            self.assertNotContains(r, reverse(
                'admin_portal:student_attendance_record_delete', args=[rec.pk]))
            self.assertNotContains(r, reverse(
                'admin_portal:attendance_record_edit_note', args=[rec.pk]))
        self.assertNotContains(r, reverse(
            'admin_portal:student_history', args=[self.student.pk]))

    def test_supervisor_teachers_tab_has_no_edit_delete_add(self):
        r = self.client.get(self.url, {'tab': 'teachers'})
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'teacher-edit/')
        self.assertNotContains(r, 'teacher-delete/')
        self.assertNotContains(r, reverse(
            'admin_portal:teacher_add_excused_absence'))

    def test_supervisor_can_export(self):
        r = self.client.get(self.export_url, {'tab': 'students'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(self._rows(r)), 5)
        r = self.client.get(
            self.export_url, {'tab': 'teachers', 'format': 'pivot'})
        self.assertEqual(r.status_code, 200)

    def test_supervisor_cannot_delete_or_edit_via_post(self):
        rec = self.student_recs[0]
        r = self.client.post(reverse(
            'admin_portal:student_attendance_record_delete', args=[rec.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            StudentAttendanceRecord.objects.filter(pk=rec.pk).exists())

        r = self.client.post(reverse(
            'admin_portal:attendance_record_edit_note', args=[rec.pk]),
            {'teacher_note': 'hacked'})
        rec.refresh_from_db()
        self.assertEqual(rec.teacher_note, 'ملاحظة')

        trec = TeacherAttendanceRecord.objects.first()
        self.client.post(reverse(
            'admin_portal:teacher_attendance_record_delete', args=[trec.pk]))
        self.assertTrue(
            TeacherAttendanceRecord.objects.filter(pk=trec.pk).exists())

        self.client.post(reverse('admin_portal:teacher_add_excused_absence'),
                         {'teacher_id': str(self.sub.id), 'date': '2025-07-02'})
        self.assertFalse(TeacherAttendanceRecord.objects.filter(
            teacher=self.sub).exists())

    def test_admin_still_has_controls(self):
        self.client.logout()
        self.client.login(phone='02100000000', password='adminpass')
        r = self.client.get(self.url)
        self.assertFalse(r.context['read_only'])
        self.assertContains(r, reverse(
            'admin_portal:student_attendance_record_delete', args=[self.student_recs[0].pk]))

    def test_teacher_still_denied(self):
        self.client.logout()
        self.client.login(phone='02122222222', password='tpass')
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.get(self.export_url).status_code, 302)


class SpecificDatesFilterTests(_Base):

    def setUp(self):
        super().setUp()
        self.client.login(phone='02100000000', password='adminpass')

    def test_students_tab_specific_dates(self):
        r = self.client.get(self.url, {'dates': '2025-07-01,2025-07-05'})
        self.assertEqual(r.context['student_total'], 2)
        self.assertEqual(r.context['selected_dates'], [
                         '2025-07-01', '2025-07-05'])

    def test_teachers_tab_specific_dates(self):
        r = self.client.get(
            self.url, {'tab': 'teachers', 'dates': '2025-07-03'})
        self.assertEqual(r.context['teacher_total'], 1)

    def test_invalid_dates_ignored(self):
        r = self.client.get(
            self.url, {'dates': 'garbage,2025-07-07,2025-13-40'})
        self.assertEqual(r.context['student_total'], 1)

    def test_dates_combined_with_range(self):
        r = self.client.get(self.url, {
            'dates': '2025-07-01,2025-07-05', 'date_from': '2025-07-04'})
        self.assertEqual(r.context['student_total'], 1)

    def test_supervisor_can_use_dates_filter(self):
        self.client.logout()
        self.client.login(phone='02111111111', password='suppass')
        r = self.client.get(self.url, {'dates': '2025-07-01,2025-07-07'})
        self.assertEqual(r.context['student_total'], 2)

    def test_export_students_specific_dates(self):
        r = self.client.get(self.export_url, {
            'tab': 'students', 'dates': '2025-07-01,2025-07-07'})
        rows = self._rows(r)
        self.assertEqual(len(rows), 3)
        self.assertEqual({rows[1][0], rows[2][0]}, {
                         '2025-07-01', '2025-07-07'})

    def test_export_teachers_old_specific_dates(self):
        r = self.client.get(self.export_url, {
            'tab': 'teachers', 'format': 'old', 'dates': '2025-07-03'})
        rows = self._rows(r)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], '2025-07-03')

    def test_export_pivot_uses_only_selected_dates_as_columns(self):
        r = self.client.get(self.export_url, {
            'tab': 'teachers', 'format': 'pivot', 'dates': '2025-07-01,2025-07-07'})
        rows = self._rows(r)
        header1 = [c for c in rows[0] if c]
        self.assertEqual(
            header1, ['المعلم', '2025-07-01', '2025-07-07', 'متوسط التقييم'])
        teacher_row = next(row for row in rows if row[0] == 'معلم أصلي')
        # check-in for both selected days present, not 'absent'
        self.assertEqual(teacher_row[1], '07:45')
        self.assertEqual(teacher_row[4], '07:45')


class AttendanceExportCompletenessTests(_Base):

    def setUp(self):
        super().setUp()
        self.client.login(phone='02100000000', password='adminpass')

    def test_student_export_contains_all_fields(self):
        r = self.client.get(
            self.export_url, {'tab': 'students', 'dates': '2025-07-01'})
        header, row = self._rows(r)
        data = dict(zip(header, row))
        self.assertEqual(data['التاريخ'], '2025-07-01')
        self.assertEqual(data['اسم الطالب'], 'طالب التواريخ')
        self.assertEqual(data['الرقم القومي'], '60000000000001')
        self.assertEqual(data['الكود'], 'DTS001')
        self.assertEqual(data['الصف'], 'الصف الأول')
        self.assertTrue(data['وقت الحضور'])
        self.assertTrue(data['وقت المغادرة'])
        self.assertEqual(data['مدة الحضور'], '2س 30د')
        self.assertEqual(data['المعلم المكلف'], 'معلم بديل')
        self.assertEqual(data['التقييم'], 8)
        self.assertEqual(data['نيابة'], 'نعم')
        self.assertEqual(data['ملاحظات'], 'غياب')
        self.assertEqual(data['ملاحظة المعلم'], 'ملاحظة')
        self.assertEqual(data['المعلم الأصلي (الغائب)'], 'معلم أصلي')
        self.assertEqual(data['صورة الواجب'], 'لا')
        self.assertEqual(data['صورة الاختبار'], 'لا')

    def test_student_export_row_count_matches_list(self):
        params = {'tab': 'students', 'teacher': str(self.sub.id)}
        list_total = self.client.get(self.url, params).context['student_total']
        rows = self._rows(self.client.get(self.export_url, params))
        self.assertEqual(len(rows) - 1, list_total)

    def test_teacher_export_row_count_matches_list(self):
        params = {'tab': 'teachers', 'format': 'old'}
        list_total = self.client.get(self.url, params).context['teacher_total']
        rows = self._rows(self.client.get(self.export_url, params))
        self.assertEqual(len(rows) - 1, list_total)
