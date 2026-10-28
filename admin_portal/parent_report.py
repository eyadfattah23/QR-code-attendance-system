"""Parent progress report: data assembly and PDF rendering.

One document template renders both in the browser (preview) and through
WeasyPrint (PDF download), so this module only produces plain data.

Absences are inferred: a subject "held a session" on a day when at least one
student attended it (records with that original teacher). Days with no
records at all are not sessions. A session counts for this student only from
the earlier of their first attendance in that subject or the date they were
linked to its teacher.
"""

import datetime
import math
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

from django.contrib.staticfiles import finders
from django.core.files.storage import default_storage
from django.db.models import Avg, Min
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils._os import safe_join
from django.utils.timezone import localdate, localtime

from attendance.models import StudentAttendanceRecord
from core.models import StudentTeacherLink

# Rating tiers. The default rating is 6, so 5 or less means the teacher
# actively lowered it.
RATING_LOW_MAX = 5
RATING_MID_MAX = 7

# Display priority: low days first, then distinguished days, then ordinary.
TIER_ORDER = {'low': 0, 'high': 1, 'mid': 2}

MAX_PERIOD_DAYS = 366

ARABIC_WEEKDAYS = (
    'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد',
)


def rating_tier(rating):
    """Return 'low', 'mid' or 'high' for a 1–10 rating."""
    if rating <= RATING_LOW_MAX:
        return 'low'
    if rating <= RATING_MID_MAX:
        return 'mid'
    return 'high'


def _parse_date(value):
    try:
        return datetime.datetime.strptime((value or '').strip(), '%Y-%m-%d').date()
    except ValueError:
        return None


def parse_period(params, today=None):
    """Read date_from/date_to from a QueryDict-like mapping.

    Defaults to the current month up to today; swaps reversed ranges and caps
    the length at MAX_PERIOD_DAYS (keeping the end date).
    """
    today = today or localdate()
    date_from = _parse_date(params.get('date_from'))
    date_to = _parse_date(params.get('date_to')) or today
    if date_from is None:
        date_from = date_to.replace(day=1)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    if (date_to - date_from).days >= MAX_PERIOD_DAYS:
        date_from = date_to - datetime.timedelta(days=MAX_PERIOD_DAYS - 1)
    return date_from, date_to


def month_period(day, today=None):
    """The calendar month containing `day`, ending no later than today."""
    today = today or localdate()
    first = day.replace(day=1)
    next_month = (first + datetime.timedelta(days=32)).replace(day=1)
    last = next_month - datetime.timedelta(days=1)
    return first, max(first, min(last, today))


def report_presets(today=None):
    """Quick date ranges offered next to the report date pickers."""
    today = today or localdate()
    month_start = today.replace(day=1)
    last_month_end = month_start - datetime.timedelta(days=1)
    return [
        {'label': 'هذا الشهر', 'from': month_start, 'to': today},
        {'label': 'الشهر الماضي', 'from': last_month_end.replace(day=1), 'to': last_month_end},
        {'label': 'آخر 30 يوماً', 'from': today - datetime.timedelta(days=29), 'to': today},
        {'label': 'آخر 3 أشهر', 'from': today - datetime.timedelta(days=89), 'to': today},
    ]


def _arabic_count(n, one, two, few, many):
    """Arabic noun agreement: 1 → one, 2 → two, 3–10 → few, 11+ → many."""
    if n == 1:
        return one
    if n == 2:
        return two
    if 3 <= n % 100 <= 10:
        return f'{n} {few}'
    return f'{n} {many}'


def _unit(n, single, few, many):
    """Arabic counted-noun form to print after a numeral."""
    if 3 <= n % 100 <= 10:
        return few
    return many if n > 10 else single


def _rows(items, size):
    """Split into rows of `size`, padding the last row with None.

    Fixed-width cells spread with space-between need the padding so a short
    last row keeps the same column positions (in WeasyPrint and browsers).
    """
    rows = [items[i:i + size] for i in range(0, len(items), size)]
    if rows:
        rows[-1] = rows[-1] + [None] * (size - len(rows[-1]))
    return rows


def _fmt(value):
    """One-decimal number without locale formatting ("7.0" → "7")."""
    text = f'{value:.1f}'
    return text[:-2] if text.endswith('.0') else text


def _subject_titles(teacher):
    """(title, subtitle) for a subject block."""
    if teacher.is_course:
        return teacher.full_name, 'كورس'
    if teacher.subject:
        return teacher.subject, f'المعلم: {teacher.full_name}'
    return teacher.full_name, ''


def _decorate(record):
    """Attach display helpers used by the template."""
    record.tier = rating_tier(record.rating)
    record.weekday = ARABIC_WEEKDAYS[record.date.weekday()]
    record.note = (record.teacher_note or '').strip()
    teacher = record.original_teacher or record.assigned_teacher
    record.subject_title = _subject_titles(teacher)[0] if teacher else '—'
    rated_by = record.assigned_teacher or record.original_teacher
    record.teacher_name = rated_by.full_name if rated_by else ''
    return record


def _build_subjects(student, records, date_from, date_to):
    links = list(
        StudentTeacherLink.objects.filter(student=student).select_related('teacher')
    )
    teachers = {link.teacher_id: link.teacher for link in links}
    linked_since = {
        link.teacher_id: localtime(link.created_at).date() for link in links
    }
    primary_ids = {link.teacher_id for link in links if link.is_primary}
    for rec in records:
        if rec.original_teacher_id:
            teachers.setdefault(rec.original_teacher_id, rec.original_teacher)

    first_seen = dict(
        StudentAttendanceRecord.objects
        .filter(student=student, original_teacher_id__in=teachers)
        .values('original_teacher_id')
        .annotate(first=Min('date'))
        .values_list('original_teacher_id', 'first')
    )
    held = defaultdict(set)
    for teacher_id, day in (
        StudentAttendanceRecord.objects
        .filter(original_teacher_id__in=teachers, date__range=(date_from, date_to))
        .values_list('original_teacher_id', 'date')
        .distinct()
    ):
        held[teacher_id].add(day)

    subjects = []
    for teacher_id, teacher in teachers.items():
        own = {r.date: r for r in records if r.original_teacher_id == teacher_id}
        starts = [d for d in (first_seen.get(teacher_id),
                              linked_since.get(teacher_id)) if d]
        start = min(starts) if starts else date_from
        days = sorted({d for d in held[teacher_id] if d >= start} | set(own))
        if not days and not (teacher_id in linked_since and teacher.is_active):
            continue
        sessions = [{'date': d, 'record': own.get(d)} for d in days]
        ratings = [r.rating for r in own.values()]
        title, subtitle = _subject_titles(teacher)
        subjects.append({
            'title': title,
            'subtitle': subtitle,
            'is_primary': teacher_id in primary_ids,
            'sessions': sessions,
            'held': len(sessions),
            'attended': len(own),
            'absent': len(sessions) - len(own),
            'rate': round(len(own) * 100 / len(sessions)) if sessions else None,
            'avg': _fmt(sum(ratings) / len(ratings)) if ratings else None,
            'avg_tier': rating_tier(sum(ratings) / len(ratings)) if ratings else None,
        })

    # Attendance not tied to a course (scanned with no teacher).
    loose = [r for r in records if not r.original_teacher_id]
    if loose:
        ratings = [r.rating for r in loose]
        subjects.append({
            'title': 'حضور عام', 'subtitle': 'بدون مادة محددة',
            'is_primary': False,
            'sessions': [{'date': r.date, 'record': r} for r in loose],
            'held': len(loose), 'attended': len(loose), 'absent': 0, 'rate': 100,
            'avg': _fmt(sum(ratings) / len(ratings)),
            'avg_tier': rating_tier(sum(ratings) / len(ratings)),
        })

    subjects.sort(key=lambda s: (not s['is_primary'], s['title']))
    return subjects


def _build_chart(records, avg, prev_avg):
    """SVG geometry for the rating trend. Time runs right-to-left (RTL)."""
    if not records:
        return None
    width, height = 720, 206
    left, right = 34, 680
    top, bottom = 22, 166          # y of rating 10 and rating 1
    unit = (bottom - top) / 9

    def y(value):
        return round(top + (10 - value) * unit, 1)

    n = len(records)
    step = (right - left) / (n - 1) if n > 1 else 0
    label_every = max(1, math.ceil(n / 12))
    points, labelled_dates = [], set()
    for i, rec in enumerate(records):
        x = round(right - i * step, 1) if n > 1 else (left + right) / 2
        show_label = (i % label_every == 0 or i == n - 1) and rec.date not in labelled_dates
        if show_label:
            labelled_dates.add(rec.date)
        points.append({
            'x': x, 'y': y(rec.rating), 'rating': rec.rating, 'tier': rec.tier,
            'date_label': f'{rec.date.day}/{rec.date.month}' if show_label else '',
        })

    avg_y = y(avg)
    prev_y = y(prev_avg) if prev_avg is not None else None
    # Keep the two reference labels from overlapping.
    avg_label_y, prev_label_y = avg_y - 5, (prev_y - 5) if prev_y is not None else None
    if prev_y is not None and abs(avg_y - prev_y) < 13:
        if avg_y <= prev_y:
            prev_label_y = prev_y + 13
        else:
            avg_label_y = avg_y + 13

    return {
        'width': width, 'height': height,
        'left': left, 'right': right, 'plot_width': right - left,
        'line': ' '.join(f"{p['x']},{p['y']}" for p in points),
        'points': points,
        'grid': [{'value': v, 'y': y(v)} for v in (10, 8, 6, 4, 2)],
        'high_band': {'y': y(10.5), 'h': round(y(7.5) - y(10.5), 1)},
        'low_band': {'y': y(5.5), 'h': round(y(0.5) - y(5.5), 1)},
        'avg': {'y': avg_y, 'label_y': avg_label_y, 'text': _fmt(avg)},
        'prev': ({'y': prev_y, 'label_y': prev_label_y, 'text': _fmt(prev_avg)}
                 if prev_y is not None else None),
        'x_label_y': height - 8,
    }


def _summary(student, held, attended, avg, low_count):
    name = student.nickname or student.full_name.split()[0]
    female = student.gender == 'F'
    if not held:
        return [f'لم تُسجَّل أي حصص {"للطالبة" if female else "للطالب"} خلال هذه الفترة.']
    verb = 'حضرت' if female else 'حضر'
    sessions = _arabic_count(held, 'حصة واحدة', 'حصتين', 'حصص', 'حصة')
    first = f'خلال هذه الفترة {verb} {name} {attended} من أصل {sessions}'
    if avg is not None:
        first += f'، بمتوسط تقييم {_fmt(avg)} من 10'
    lines = [first + '.']
    if low_count:
        days = _arabic_count(low_count, 'يوم واحد', 'يومان', 'أيام', 'يوماً')
        needs = {1: 'يحتاج', 2: 'يحتاجان'}.get(low_count, 'تحتاج')
        lines.append(
            f'سُجِّل {days} بتقييم منخفض {needs} إلى متابعة، '
            'ونرجو الاطلاع على ملاحظات المعلمين أدناه.'
        )
    elif attended:
        lines.append('لم يُسجَّل أي يوم بتقييم منخفض — نشكر لكم حسن المتابعة.')
    return lines


def build_parent_report(student, date_from, date_to):
    """Assemble everything the parent report template needs."""
    records = [
        _decorate(r) for r in (
            StudentAttendanceRecord.objects
            .filter(student=student, date__range=(date_from, date_to))
            .select_related('original_teacher', 'assigned_teacher')
            .order_by('date', 'check_in_time')
        )
    ]
    ratings = [r.rating for r in records]
    avg = sum(ratings) / len(ratings) if ratings else None

    period_days = (date_to - date_from).days + 1
    prev_to = date_from - datetime.timedelta(days=1)
    prev_from = prev_to - datetime.timedelta(days=period_days - 1)
    prev_avg = (
        StudentAttendanceRecord.objects
        .filter(student=student, date__range=(prev_from, prev_to))
        .aggregate(avg=Avg('rating'))['avg']
    )
    delta = round(avg - prev_avg, 1) if avg is not None and prev_avg is not None else None

    subjects = _build_subjects(student, records, date_from, date_to)
    held = sum(s['held'] for s in subjects)
    attended = sum(s['attended'] for s in subjects)

    by_tier = defaultdict(list)
    for rec in records:
        by_tier[rec.tier].append(rec)

    def priority(rec):
        return (TIER_ORDER[rec.tier], rec.date, rec.check_in_time)

    # Low-rating exams get larger two-up cards; the rest go three-up.
    exams = sorted((r for r in records if r.test_photo), key=priority)
    exam_rows = (
        [{'cols': 2, 'items': row} for row in _rows([r for r in exams if r.tier == 'low'], 2)]
        + [{'cols': 3, 'items': row} for row in _rows([r for r in exams if r.tier != 'low'], 3)]
    )
    high_without_note = sum(1 for r in by_tier['high'] if not r.note)

    return {
        'student': student,
        'date_from': date_from,
        'date_to': date_to,
        'period_days': period_days,
        'period_days_unit': _unit(period_days, 'يوم', 'أيام', 'يوماً'),
        'generated_on': localdate(),
        'summary': _summary(student, held, attended, avg, len(by_tier['low'])),
        'stats': {
            'avg': _fmt(avg) if avg is not None else None,
            'avg_tier': rating_tier(avg) if avg is not None else None,
            'prev_avg': _fmt(prev_avg) if prev_avg is not None else None,
            'delta': _fmt(abs(delta)) if delta is not None else None,
            'delta_sign': (0 if not delta else (1 if delta > 0 else -1)),
            'held': held,
            'attended': attended,
            'absent': held - attended,
            'rate': round(attended * 100 / held) if held else None,
            'held_unit': _unit(held, 'حصة', 'حصص', 'حصة'),
            'days_present': len({r.date for r in records}),
            'low': len(by_tier['low']),
            'low_unit': _unit(len(by_tier['low']), 'يوم', 'أيام', 'يوماً'),
            'mid': len(by_tier['mid']),
            'high': len(by_tier['high']),
            'high_unit': _unit(len(by_tier['high']), 'يوم', 'أيام', 'يوماً'),
            'total': len(records),
            'total_text': _arabic_count(len(records), 'تقييم واحد', 'تقييمان', 'تقييمات', 'تقييماً'),
        },
        'chart': _build_chart(records, avg, prev_avg),
        'subjects': subjects,
        'exams': exams,
        'exam_rows': exam_rows,
        'low_days': by_tier['low'],
        'high_note_rows': _rows([r for r in by_tier['high'] if r.note], 2),
        'high_without_note_text': (
            'إضافة إلى ' + _arabic_count(
                high_without_note, 'يوم متميز آخر', 'يومين متميزين آخرين',
                'أيام متميزة أخرى', 'يوماً متميزاً آخر')
            + ' بدون ملاحظات.'
        ) if high_without_note else '',
        'mid_notes': [r for r in by_tier['mid'] if r.note],
        'rating_low_max': RATING_LOW_MAX,
        'rating_mid_max': RATING_MID_MAX,
    }


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------

# Placeholder origin: the document is rendered with the same root-relative
# /static/ and /media/ URLs the browser preview uses, and the fetcher maps
# them back onto disk. Nothing is ever fetched over the network.
_PDF_BASE_URL = 'http://parent-report.local/'


def _local_asset_fetcher():
    from weasyprint.urls import URLFetcher, URLFetchingError

    static_prefix = urlsplit(static('')).path
    media_prefix = urlsplit(default_storage.url('')).path

    class LocalAssetFetcher(URLFetcher):
        def fetch(self, url, headers=None):
            if url.startswith('data:'):
                return super().fetch(url, headers)
            parts = urlsplit(url)
            path = unquote(parts.path)
            file_path = None
            if url.startswith(_PDF_BASE_URL):
                if path.startswith(media_prefix):
                    file_path = safe_join(default_storage.location,
                                          path[len(media_prefix):])
                elif path.startswith(static_prefix):
                    file_path = finders.find(path[len(static_prefix):])
            if not file_path or not Path(file_path).is_file():
                raise URLFetchingError(f'Asset not available for PDF: {url}')
            response = super().fetch(Path(file_path).as_uri(), headers)
            # Keep the virtual URL so relative references inside stylesheets
            # (e.g. the icon font) resolve through this fetcher too.
            response.url = url
            return response

    return LocalAssetFetcher(allowed_protocols={'file', 'data'})


def render_parent_report_pdf(context):
    """Render the report to PDF bytes."""
    from weasyprint import HTML

    html = render_to_string('admin_portal/parent_report/pdf.html', context)
    return HTML(
        string=html, base_url=_PDF_BASE_URL, url_fetcher=_local_asset_fetcher(),
    ).write_pdf(optimize_images=True, jpeg_quality=72, dpi=160)
