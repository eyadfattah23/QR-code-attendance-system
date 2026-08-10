# Implementation Plan V3: Courses, Payments & Assistants (Failure-Hardened)

This document is a step-by-step implementation guide for an AI Agent. It supersedes `courses_plan_v2.md`. It keeps the same minimalist architecture — a "Course" is simply a `Teacher` row, and multi-course same-day attendance is handled via a session dropdown at the shared admin scan station — but adds explicit handling for every edge case identified during review (NULL-bypassed uniqueness, ambiguous checkouts, per-course dict collisions, race conditions, and payment-history-destroying cascades).

**Non-negotiable global rules for the implementing agent:**
- Do **not** backfill or modify `original_teacher` (or any other field) on any pre-existing attendance row. All schema changes in this plan are additive or metadata-only. Existing rows must remain byte-for-byte unchanged in content.
- Never use `.get(student=..., date=...)` on `StudentAttendanceRecord` after Phase 2 — always use `.filter(...).first()` or explicit multi-row handling, since a student can now have more than one row per day.
- Every attendance-related user-facing message must name the course it acted on, so staff always know which session was touched.

---

## Phase 1 — Photo Field Split (Homework & Test Pages)

**Goal**: Replace the single `daily_photo` with two optional image fields: `homework_photo` and `test_photo`.

**Steps to Implement:**
1. **Models:** In `attendance/models.py`, modify `StudentAttendanceRecord`:
   - Rename `daily_photo` to `homework_photo` using a Django `RenameField` migration (metadata-only — preserves existing files and DB values exactly).
   - Update its `help_text` to `'صفحة الواجب — Homework page photo'`.
   - Add `test_photo = models.ImageField(upload_to='attendance/test_photos/%Y/%m/%d/', null=True, blank=True, help_text='صفحة الاختبار — Test page photo')`.
2. **Migration:** Run `python manage.py makemigrations`. **Important:** Edit the generated migration file to ensure it uses `migrations.RenameField` for `daily_photo` → `homework_photo` (not a drop+add). Run `python manage.py migrate`.
3. **Fix every remaining `daily_photo` reference** (do not skip any — a rename with dangling references will crash the app):
   - `admin_portal/views.py` — `dashboard()`'s `today_missing_photos_count` filter (`Q(daily_photo__isnull=True) | Q(daily_photo='')`) → change to check both `homework_photo` and `test_photo` (decide and state explicitly whether "missing photos" means missing *either* or missing *both*; recommended: missing homework_photo, since that's the primary required one).
   - `admin_portal/views.py` — `attendance_record_edit_photo` view: currently hardcodes `daily_photo` in both the delete-old-file and save-new-file branches. Add an explicit `photo_field` parameter (`request.POST.get('photo_field')`, restricted to `{'homework_photo', 'test_photo'}`) so the view knows which of the two fields is being replaced/removed — never infer this.
   - `teacher_portal/views.py` — `upload_photo` view: same fix, explicit field discriminator instead of a single hardcoded `photo`/`daily_photo` name.
   - `teacher_portal/tests/test_views.py` — update all `record.daily_photo` references to `record.homework_photo`.
4. **Templates:**
   - `templates/teacher_portal/upload_photo.html`: split into two upload sections ("صفحة الواجب" and "صفحة الاختبار"), each posting its own `photo_field` value.
   - `templates/teacher_portal/dashboard.html`: display thumbnails/icons for both photos independently (a course may have a homework photo but no test photo, or vice versa).
   - `templates/admin_portal/attendance_records.html` and both `student_history.html` templates (admin + teacher portal): update references from `daily_photo` to `homework_photo`, add a column/badge for `test_photo`.

---

## Phase 2 — Multi-Course Attendance (Scan Station Dropdown + Safe Constraint)

**Goal**: Allow a student to have independent attendance rows per course on the same day, with zero ambiguous or silently-wrong outcomes at any entry point.

### 2.1 — Database constraints
In `attendance/models.py`, modify `StudentAttendanceRecord.Meta.constraints`:
- Replace `UniqueConstraint(fields=['student', 'date'], name='unique_student_attendance_per_day')` with:
  ```python
  models.UniqueConstraint(
      fields=['student', 'date', 'original_teacher'],
      name='unique_student_attendance_per_day_per_course',
  ),
  models.UniqueConstraint(
      fields=['student', 'date'],
      condition=models.Q(original_teacher__isnull=True),
      name='unique_student_attendance_per_day_no_course',
  ),
  ```
  The second constraint is required because Postgres treats `NULL <> NULL`, so the first constraint alone would silently allow duplicate rows for students with no course assigned. This is a widening of the old constraint — every existing row already satisfies both (verified: the old constraint already guaranteed at most one row per student per day, so at most one `original_teacher` value existed per day per student already).
- Run `makemigrations` and `migrate`. Confirm in the migration file that this is a pure constraint swap — no `RunPython`/data migration, no column changes.

### 2.2 — Add a lightweight course/teacher distinction (for dropdown usability only)
In `core/models.py`, add to `Teacher`:
```python
is_course = models.BooleanField(
    default=False,
    help_text='صح إذا كان هذا السجل يمثل كورساً وليس معلماً أساسياً — للتمييز في قائمة محطة المسح فقط',
)
```
This does **not** replace or restructure the existing `subject` field, and does not require `teacher_type`/`description` from the original Gemini plan — it exists purely so the station dropdown can group/filter "courses" separately from regular teachers. Default `False` means every existing `Teacher` row is unaffected until an admin explicitly marks specific rows as courses.

### 2.3 — Station template
In `templates/scan/station.html`:
- Add `<select name="session_teacher" class="form-select">`, populated from a `courses` context variable (`Teacher.objects.filter(is_course=True).order_by('full_name')`), with a default option `"--- تلقائي (حسب الحصة المفتوحة) ---"` as the empty value.
- Keep the dropdown's selected value sticky across the page (re-render with the last-selected course after each submission), so staff scanning a whole class through one course don't have to re-select it every scan.

### 2.4 — Station view logic (`attendance/views.py`, `station_view`)
Replace the student check-in/checkout block with the following decision logic. Wrap the whole per-code block in the existing `transaction.atomic()` + `select_for_update()`, but change the lookup from `.get()` to filtering:

```python
selected_teacher_id = request.POST.get("session_teacher", "").strip()
selected_teacher = (
    Teacher.objects.filter(pk=selected_teacher_id).first()
    if selected_teacher_id else None
)

with _tx.atomic():
    open_records = list(
        StudentAttendanceRecord.objects.select_for_update()
        .filter(student=student, date=today, check_out_time__isnull=True)
        .select_related('original_teacher')
    )

    if selected_teacher is None:
        # "تلقائي" mode
        if len(open_records) == 0:
            # Check-in: resolve course from primary StudentTeacherLink, same as today
            primary_link = (
                StudentTeacherLink.objects.filter(student=student)
                .order_by("-is_primary", "created_at")
                .select_related("teacher").first()
            )
            original_teacher = primary_link.teacher if primary_link else None
            _create_checkin(student, today, original_teacher, request.user)
        elif len(open_records) == 1:
            _do_checkout(open_records[0])
        else:
            # Ambiguous — do not guess, ask staff to pick explicitly
            course_names = ", ".join(
                r.original_teacher.full_name if r.original_teacher else "بدون حصة"
                for r in open_records
            )
            results.append({
                "status": "warning",
                "label": "أكثر من حصة مفتوحة",
                "message": f"{student.full_name} - لديه أكثر من حصة مفتوحة اليوم ({course_names}) — يرجى اختيار الحصة من القائمة",
                "row_class": "warning",
            })
    else:
        # Explicit course selected
        matching = next((r for r in open_records if r.original_teacher_id == selected_teacher.id), None)
        if matching is not None:
            _do_checkout(matching)
        else:
            closed_today = StudentAttendanceRecord.objects.filter(
                student=student, date=today, original_teacher=selected_teacher,
                check_out_time__isnull=False,
            ).first()
            if closed_today is not None:
                results.append({
                    "status": "warning",
                    "label": "مغادرة مسجلة مسبقاً",
                    "message": f"{student.full_name} - غادر مسبقاً حصة {selected_teacher.full_name} الساعة {closed_today.check_out_time.strftime('%H:%M')}",
                    "row_class": "warning",
                })
            else:
                is_enrolled = StudentTeacherLink.objects.filter(student=student, teacher=selected_teacher).exists()
                if not is_enrolled:
                    results.append({
                        "status": "error",
                        "label": "غير مسجل في هذه الحصة",
                        "message": f"{student.full_name} - غير مسجل في حصة {selected_teacher.full_name}. اضغط 'تسجيل على أي حال' للتأكيد",
                        "row_class": "danger",
                        "allow_force": True,
                        "force_student_id": str(student.id),
                        "force_teacher_id": str(selected_teacher.id),
                    })
                else:
                    try:
                        _create_checkin(student, today, selected_teacher, request.user)
                    except IntegrityError:
                        # Lost a race to a concurrent scan for the same student/course/day
                        results.append({
                            "status": "warning",
                            "label": "تم التسجيل من جهاز آخر",
                            "message": f"{student.full_name} - تم تسجيل حضور حصة {selected_teacher.full_name} للتو من محطة أخرى",
                            "row_class": "warning",
                        })
```

Notes:
- `_create_checkin` and `_do_checkout` are small helpers factoring out the existing check-in/checkout code (time-skew check, 5-minute-minimum check, `duration_display` message) so both the "تلقائي" and "explicit course" branches reuse identical logic instead of duplicating it.
- The "غير مسجل" (not enrolled) path is a **hard stop by default**, with an explicit force-confirm affordance in the UI (a second button in the result row that resubmits with a `force=1` flag) — never silently allowed, never silently blocked without recourse.
- Every result message includes the course name, satisfying the "always show which session was touched" rule.
- Import `IntegrityError` from `django.db` at the top of `attendance/views.py`.

### 2.5 — `teacher_portal/views.py` (`teacher_scan`) — must also be updated
This is the primary real-world entry point once courses exist (each course = its own teacher-portal login), and is currently **not touched by the old plan** — leaving it as-is would silently drop a second course's attendance. Update the `get_or_create` call:
```python
student_record, created = StudentAttendanceRecord.objects.filter(
    student=student, date=today, original_teacher=teacher,
).first(), None
```
Replace with explicit filter+create logic mirroring the station's `_create_checkin`/`_do_checkout` helpers, scoped to `original_teacher=teacher` (the acting teacher is always known here, so there is never ambiguity — no dropdown needed on this path). Handle `IntegrityError` on create the same way as 2.4.

### 2.6 — Fix per-student dict collisions across the codebase
Once a student can have 2+ rows per day, every place that builds a `{student_id: record}` dict must instead scope by course, or the wrong course's record can be shown/edited/exported:
- `teacher_portal/views.py` `dashboard()` — scope `today_attendance`/`attendance_by_student_id` to `original_teacher=teacher` (or `assigned_teacher=teacher` for substitute-covered rows), not just `date=today`.
- `teacher_portal/views.py` `export_attendance()` — same fix for `attendance_by_id`.
- `admin_portal/views.py` `teacher_mark_absent()` — same fix for `record_by_student` (filter `records_qs` by `original_teacher=teacher` in addition to `date=absence_date`).
- `teacher_portal/views.py` `dashboard()` and `export_attendance()` — the `avg_ratings` aggregate must also scope to `student_id__in=... , original_teacher=teacher` so a teacher only sees ratings from their own course, not blended across a student's other courses.

### 2.7 — Checkout across cross-entry-point mixing
No special handling needed beyond 2.4/2.5 — if a student checks in via Course A's teacher-portal login then is later scanned at the shared station in "تلقائي" mode, the station will correctly see 0 open records for Course B (since Course A's record, if still open, is the one match) and behave per the table in 2.4. Document this explicitly in code comments so future maintainers don't "fix" it into a bug.

---

## Phase 3 — Course Payments Model & Teacher Description

**Goal**: Track monthly payment status per student **per course** (a student can be paid for one course and not another), without risking cascade-deletion of financial history.

**Steps to Implement:**
1. **New Model:** In `core/models.py`, add:
   ```python
   class CoursePayment(models.Model):
       class PaymentStatus(models.TextChoices):
           NOT_PAID = 'not_paid', 'لم يُدفع'
           PARTIAL = 'partial', 'دفع جزئي'
           PAID = 'paid', 'تم الدفع'

       student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='course_payments')
       course = models.ForeignKey(
           Teacher, on_delete=models.PROTECT, related_name='course_payments',
           limit_choices_to={'is_course': True},
       )
       year = models.PositiveIntegerField()
       month = models.PositiveSmallIntegerField()  # 1–12
       status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.NOT_PAID)
       amount_paid = models.DecimalField(
           max_digits=8, decimal_places=2, null=True, blank=True,
           help_text='المبلغ المدفوع فعلياً (اختياري — للتتبع المالي إن وجد)',
       )
       note = models.TextField(blank=True, default='')
       updated_at = models.DateTimeField(auto_now=True)

       class Meta:
           db_table = 'course_payments'
           unique_together = ['student', 'course', 'year', 'month']
           ordering = ['-year', '-month']
   ```
   - `amount_paid` is optional/nullable so schools that only care about status (paid/partial/unpaid) can ignore it entirely — but the field exists from day one so bookkeeping/reporting on actual collected sums is possible later without another migration + UI rework. Summary stats in Phase 5 should sum `amount_paid` where present, in addition to the paid/partial/unpaid counts.
   - `course` uses `on_delete=models.PROTECT` (not `CASCADE`) — a course-`Teacher` with existing payment history **cannot** be hard-deleted; the admin must be blocked with a clear message ("لا يمكن حذف هذا الكورس، توجد سجلات دفع مرتبطة به") and directed to deactivate it instead (see step 2).
   - Payments should only be creatable for (student, course) pairs that exist in `StudentTeacherLink`. Enforce this in the form/view layer, not as a DB constraint, so history remains valid even if the enrollment link is later removed.
2. **Course deactivation instead of hard delete:** In `core/models.py`, add `Teacher.is_active = models.BooleanField(default=True)`. Update `admin_portal/views.py` `teacher_delete`: if the teacher has any related `CoursePayment`, `StudentTeacherLink`, or attendance records, redirect to a "deactivate" action (`is_active = False`, hidden from active dropdowns/rosters) instead of performing the destructive delete. Only allow true hard-delete when there is zero related history.
3. **Teacher Description:** In `core/models.py`, update `Teacher`:
   - Add `description = models.TextField(blank=True, default='', help_text='وصف الكورس أو ملاحظات إضافية')`.
4. **Forms:** Update `TeacherForm` in `admin_portal/forms.py` to include `description` and `is_course`. Add a `CoursePaymentForm` (student, course, year, month, status, amount_paid, note) used by the roster inline-toggle and drill-down views in Phase 5.
5. **Migrations:** Run `makemigrations` and `migrate`. Confirm `is_course` and `is_active` default to values that leave all existing `Teacher` rows behaving exactly as before (`is_course=False`, `is_active=True`).

---

## Phase 4 — Assistant Teacher Role & Portal

**Goal**: Add an `ASSISTANT` user role with a dedicated portal for acting on behalf of linked teachers/courses, reusing the existing supervisor "acting as" pattern.

**Steps to Implement:**
1. **Models:** In `core/models.py`:
   - Add `ASSISTANT = 'assistant', 'Assistant'` to `User.Role` TextChoices.
   - Add `@property def is_assistant(self): return self.role == self.Role.ASSISTANT` to `User`.
   - Create `AssistantTeacherLink` model: `user` (FK to User, CASCADE), `teacher` (FK to Teacher, CASCADE), `unique_together = ['user', 'teacher']`.
2. **New App:**
   - Create `assistant_portal` app, add to `INSTALLED_APPS`.
   - `views.py`: `dashboard`, `select_teacher` (sets `assistant_teacher_id` in session), `deselect_teacher`.
   - Dashboard must only list teachers found in `AssistantTeacherLink.objects.filter(user=request.user)`.
3. **Access control (`teacher_portal/views.py`):**
   - Update `teacher_required` to allow `request.user.is_assistant` when `assistant_teacher_id` is present in session.
   - Update `get_acting_teacher` to resolve the linked teacher for assistants — **must re-verify `AssistantTeacherLink.objects.filter(user=request.user, teacher_id=session_value).exists()` on every call**, not just once at login, so revoking a link takes effect immediately even mid-session (prevents stale-session privilege after an admin unlinks an assistant).
4. **Routing:** Update `dashboard_redirect` in `core/views.py` to route assistants to `assistant_portal`.
5. **Downstream compatibility:** Confirm `upload_photo`, `edit_record_note`, and `student_history` in `teacher_portal/views.py` work unmodified for assistants, since they already key off `get_acting_teacher()` + the record's own `pk` rather than any student-keyed dict — no additional changes needed there.

---

## Phase 5 — Admin UI Wiring & Payments Export

**Goal**: Finalize admin portal UI for assistants, course payments, and the photo split — with UX that prevents the ambiguous-state failures described in Phase 2, and a payments UI designed around the actual daily task (collecting and marking payment fast) rather than around browsing history.

**Payment UX design principles (read before implementing step 3):**
- The **course roster view is the primary, daily-use payment surface** — not the 12-month grid. Marking a payment should be a single click from the list of students already on screen, not a navigation into a dedicated per-student page.
- The 12-month grid is a **drill-down for history/audit**, reached from a roster row ("عرض السجل الكامل"), not a page staff visit routinely.
- Batch collection (a whole class paying around the same time) must be supported with one bulk action, not one click per student.
- Unpaid counts must be visible from the main admin dashboard, the same way `today_missing_photos_count` already is — this is a daily-relevant number, not something buried under a separate menu.

**Steps to Implement:**
1. **Assistant management:** CRUD pages in `admin_portal/views.py` to create/link/unlink assistants and teachers. Add sidebar link.
2. **Course flagging UI:** In the teacher create/edit form, expose the `is_course` checkbox and `is_active` toggle (with the delete-vs-deactivate branching from Phase 3 step 2 wired into the teacher list/detail actions).
3. **Course roster payment UI (primary surface):**
   - On each course's (`Teacher`) detail page, add a roster table of enrolled students (from `StudentTeacherLink`) with the **current month's** payment status shown as an inline toggle (لم يدفع / دفع جزئي / تم الدفع), saved via HTMX/AJAX with no full page reload. Clicking a status cycles it inline; no separate form page for the common case.
   - Add a bulk action above the roster: "تحديد الكل كمدفوع لهذا الشهر" — applies `status=PAID` to every currently-unpaid/partial row for the current month in this course, behind a confirm step (e.g. a confirmation modal listing how many students will be affected).
   - Each roster row has a small "عرض السجل الكامل" link that expands (inline, no page nav) or opens a modal showing that student-course's full 12-month `CoursePayment` history for edits to past months and adding notes/`amount_paid`.
   - On the student detail page, list all enrolled courses with a current-month status badge per course, linking back to that course's roster (not a separate per-student payment page) so there is one canonical place per course to manage payments.
4. **Global payments UI & export:**
   - `/portal/admin/payments/` — summary stats (paid/partial/unpaid counts, and total `amount_paid` collected where recorded) computed from `CoursePayment`, filterable by course/student/month/year/status, with Excel export. This view is for reporting/audit across courses, not for day-to-day marking — the roster view (step 3) remains the primary place payments are actually recorded.
5. **Admin dashboard visibility:** Add an unpaid-count stat (e.g. "عدد الطلاب غير المسددين هذا الشهر") to `admin_portal/dashboard.html`, linking directly to the filtered global payments view for the current month — mirrors the existing `today_missing_photos_count` pattern.
6. **Scan station UX (ties back to Phase 2):**
   - The course dropdown must only list `Teacher.objects.filter(is_course=True, is_active=True)`.
   - Every scan result row must display the course name it acted on (see 2.4).
   - The "أكثر من حصة مفتوحة" (ambiguous) and "غير مسجل في هذه الحصة" (force-confirm) result states from 2.4 need distinct visual treatment (e.g. amber/red banners with an actionable button) so front-desk staff never mistake them for a successful scan.

---

## Post-implementation verification checklist
- [ ] `python manage.py check` passes with no errors.
- [ ] `python manage.py makemigrations --check` shows no pending model changes.
- [ ] Existing single-course schools: scanning via the station in "تلقائي" mode with zero courses ever marked `is_course=True` behaves byte-for-byte identically to the pre-Phase-2 behavior (one row per student per day).
- [ ] Existing attendance rows: spot-check that `original_teacher`/`assigned_teacher`/`homework_photo` values on rows created before this migration are unchanged.
- [ ] Manually test all 7 cases in the station's course-dropdown decision table (see Phase 2.4) plus the two `teacher_scan` cases (check-in, check-out) for a student enrolled in 2 courses.
- [ ] Attempt to delete a course-`Teacher` with existing `CoursePayment` rows — confirm it's blocked with a clear message, not a cascade.
- [ ] Revoke an `AssistantTeacherLink` mid-session and confirm the assistant is immediately locked out on their next request, not just at next login.
