# Implementation Plan V2: Courses via Admin Station Dropdown, Payments & Assistants

This document serves as a step-by-step implementation guide for an AI Agent. It uses the minimalist approach: treating a "Course" simply as a `Teacher` record, and utilizing a session dropdown in the admin scan station to allow multiple same-day check-ins.

---

## Phase 1 — Photo Field Split (Homework & Test Pages)

**Goal**: Replace the single `daily_photo` with two optional image fields: `homework_photo` and `test_photo`.

**Steps to Implement:**
1. **Models:** In `attendance/models.py`, modify `StudentAttendanceRecord`:
   - Rename `daily_photo` to `homework_photo` using a Django `RenameField` migration to preserve existing photos.
   - Update its `help_text` to `'صفحة الواجب — Homework page photo'`.
   - Add `test_photo = models.ImageField(upload_to='attendance/test_photos/%Y/%m/%d/', null=True, blank=True, help_text='صفحة الاختبار — Test page photo')`.
2. **Migration:** Run `python manage.py makemigrations`. **Important:** Edit the generated migration file to ensure it uses `migrations.RenameField` for `daily_photo` -> `homework_photo`. Run `python manage.py migrate`.
3. **Templates:**
   - Modify `templates/teacher_portal/upload_photo.html`: Split into two upload sections ("صفحة الواجب" and "صفحة الاختبار").
   - Modify `templates/teacher_portal/dashboard.html`: Display thumbnails for both photos if they exist.
   - Modify `templates/admin_portal/attendance_records.html` and `student_history.html` (both portals): Update references from `daily_photo` to `homework_photo` and add displays for `test_photo`.
4. **Views:**
   - Update `upload_photo` view in `teacher_portal/views.py` and `attendance_record_edit_photo` view in `admin_portal/views.py` to handle both file fields.

---

## Phase 2 — Admin Scan Station Session Dropdown (Course Support)

**Goal**: Allow the central admin scan station to process check-ins for different courses on the same day by adding a "current session" dropdown and updating the database constraint.

**Steps to Implement:**
1. **Database Constraint:** In `attendance/models.py`, modify `StudentAttendanceRecord`:
   - Update the `UniqueConstraint` named `unique_student_attendance_per_day`. 
   - Change `fields=['student', 'date']` to `fields=['student', 'date', 'original_teacher']`.
   - Run `makemigrations` and `migrate`. This allows a student to have multiple attendance records on the same day, as long as they are for different teachers/courses.
2. **Station Template:** In `templates/scan/station.html`:
   - Add a `<select name="session_teacher" class="form-select">` dropdown inside the scan form.
   - Populate it with all `Teacher` records (e.g., passing `teachers` in the context from `views.py`). Include a default empty option like "--- الحصة الافتراضية (تلقائي) ---".
3. **Station View Logic:** In `attendance/views.py`, update `station_view`:
   - Read `selected_teacher_id = request.POST.get("session_teacher", "").strip()`.
   - Fetch the `selected_teacher = Teacher.objects.filter(pk=selected_teacher_id).first() if selected_teacher_id else None`.
   - Modify the `original_teacher` assignment: `original_teacher = selected_teacher or (primary_link.teacher if primary_link else None)`.
   - **CRITICAL UPDATE FOR CHECK-OUT**: When looking up an existing record to process a check-out, you MUST include `original_teacher` in the `.get()` query to avoid `MultipleObjectsReturned` crashes:
     ```python
     student_record = StudentAttendanceRecord.objects.select_for_update().get(
         student=student,
         date=today,
         original_teacher=original_teacher
     )
     ```

---

## Phase 3 — Course Payments Model & Teacher Description

**Goal**: Track monthly payment status per student **per course**, since a student enrolled in multiple courses (e.g. Qur'an + Math) can have independent, differing payment status for each. A flat set of 12 fields on `Student` cannot represent this, so payments are modeled as their own table keyed on the (student, course) enrollment rather than on the student alone. Also add a description field to Teachers.

**Steps to Implement:**
1. **New Model:** In `core/models.py`, add:
   ```python
   class CoursePayment(models.Model):
       class PaymentStatus(models.TextChoices):
           NOT_PAID = 'not_paid', 'لم يُدفع'
           PARTIAL = 'partial', 'دفع جزئي'
           PAID = 'paid', 'تم الدفع'

       student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='course_payments')
       course = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='course_payments')
       year = models.PositiveIntegerField()
       month = models.PositiveSmallIntegerField()  # 1–12
       status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.NOT_PAID)
       note = models.TextField(blank=True, default='')
       updated_at = models.DateTimeField(auto_now=True)

       class Meta:
           db_table = 'course_payments'
           unique_together = ['student', 'course', 'year', 'month']
           ordering = ['-year', '-month']
   ```
   - `course` is a plain FK to `Teacher` — same "course = Teacher row" convention used in Phase 2. No new `teacher_type` field is introduced; any `Teacher` can be a payment target.
   - Payments should only be creatable for pairs that already exist in `StudentTeacherLink` (i.e. the student is actually enrolled in that course). Enforce this in the form/view layer, not as a DB constraint, so payment history is preserved even if the enrollment link is later removed.
2. **Teacher Description:** In `core/models.py`, update `Teacher`:
   - Add `description = models.TextField(blank=True, default='', help_text='وصف الكورس أو ملاحظات إضافية')`.
3. **Forms:** Update `TeacherForm` in `admin_portal/forms.py` to include the `description` field. Add a `CoursePaymentForm` (student, course, year, month, status, note) used by the per-enrollment payment grid in Phase 5.
4. **Migrations:** Run `makemigrations` and `migrate`.

---

## Phase 4 — Assistant Teacher Role & Portal

**Goal**: Add an `ASSISTANT` user role with a dedicated portal for acting on behalf of linked teachers/courses.

**Steps to Implement:**
1. **Models:** In `core/models.py`:
   - Add `ASSISTANT = 'assistant', 'Assistant'` to `User.Role` TextChoices.
   - Add `@property def is_assistant(self): return self.role == self.Role.ASSISTANT` to `User`.
   - Create `AssistantTeacherLink` model: fields `user` (FK to User), `teacher` (FK to Teacher), `unique_together = ['user', 'teacher']`.
2. **New App:** 
   - Create a new Django app `assistant_portal` and add to `INSTALLED_APPS`.
   - Create `views.py` with `dashboard`, `select_teacher` (sets `assistant_teacher_id` in session), and `deselect_teacher`.
   - The dashboard must ONLY list teachers found in `AssistantTeacherLink.objects.filter(user=request.user)`.
3. **Access Control (Teacher Portal):** 
   - In `teacher_portal/views.py`, update the `teacher_required` decorator to allow `request.user.is_assistant` if they have an `assistant_teacher_id` in session.
   - Update `get_acting_teacher` to return the linked teacher for assistants (always query `AssistantTeacherLink` to verify the link exists and prevent session spoofing).
4. **Routing:** In `core/views.py`, update `dashboard_redirect` to route assistants to their new portal.

---

## Phase 5 — Admin UI Wiring & Payments Export

**Goal**: Finalize admin portal UI for Assistants and Payments.

**Steps to Implement:**
1. **Assistant Management:** Add CRUD pages for assistants in `admin_portal/views.py`, including UI to link/unlink them from teachers. Add a link to this in the admin sidebar.
2. **Per-Enrollment Payment UI:** 
   - Create `/portal/admin/students/<id>/courses/<teacher_id>/payments/` view and template, reachable only for courses the student is actually linked to via `StudentTeacherLink`.
   - Display a 12-month grid scoped to that single course, backed by `CoursePayment` rows. Each month has status buttons ( لم يدفع / دفع جزئي / تم الدفع ) and a note textarea. Save via HTMX/AJAX or a standard form submission.
   - On the student detail page, list all enrolled courses (from `StudentTeacherLink`), each with a link to its own payment grid and a current-month status badge.
   - On each course's (`Teacher`) detail page, add a roster table of enrolled students with a current-month payment status column, so staff can see who hasn't paid *that specific course* at a glance.
3. **Global Payments UI & Export:** 
   - Create `/portal/admin/payments/` view and template. Add it to the admin sidebar.
   - Add summary stats (paid/partial/unpaid counts), computed from `CoursePayment`.
   - Add a table filtering by course, student, month/year, and payment status.
   - Add an Excel Export button to download the filtered dataset.
