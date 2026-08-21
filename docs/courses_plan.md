# Implementation Plan: Course Management, Payments & Assistant Teachers

This document serves as a step-by-step implementation guide for an AI Agent. It introduces 7 major feature areas to the QR Code Attendance System. **CRITICAL:** Preserve all existing data and minimize structural changes. Old records must not be affected by these additions.

---

## Phase 1 — Photo Field Split (Homework & Test Pages)

**Goal**: Replace the single `daily_photo` with two optional image fields: `homework_photo` and `test_photo`.

**Steps to Implement:**
1. **Models:** In `attendance/models.py`, modify `StudentAttendanceRecord`:
   - Rename `daily_photo` to `homework_photo` using a Django `RenameField` migration to preserve existing photos.
   - Update its `help_text` to `'صفحة الواجب — Homework page photo'`.
   - Add `test_photo = models.ImageField(upload_to='attendance/test_photos/%Y/%m/%d/', null=True, blank=True, help_text='صفحة الاختبار — Test page photo')`.
2. **Migration:** Run `python manage.py makemigrations`. **Important:** Edit the generated migration file to ensure it uses `migrations.RenameField` for `daily_photo` -> `homework_photo` rather than removing and adding the field. Then run `python manage.py migrate`.
3. **Templates:**
   - Modify `templates/teacher_portal/upload_photo.html`: Split the single upload form into two side-by-side upload sections ("صفحة الواجب" and "صفحة الاختبار"). Each needs its own file input, preview, and submission logic.
   - Modify `templates/teacher_portal/dashboard.html`: Update to display thumbnails for both photos if they exist.
   - Modify `templates/admin_portal/attendance_records.html` and `student_history.html` (both admin and teacher portals): Update references from `daily_photo` to `homework_photo` and add displays for `test_photo`.
4. **Views:**
   - Update `upload_photo` view in `teacher_portal/views.py` to handle both file fields.
   - Update `attendance_record_edit_photo` view in `admin_portal/views.py`.
5. **Testing:** Run `pytest` to ensure no regressions.

---

## Phase 2 — New Lookup Models (SchoolGrade, Subject, TeacherSubjectGrade)

**Goal**: Create structured lookup tables for school grades and subjects, with a 3-way link to teachers.

**Steps to Implement:**
1. **Models:** In `core/models.py`:
   - Add `SchoolGrade` model: fields `name` (CharField, unique), `ordering` (PositiveIntegerField), `created_at`.
   - Add `Subject` model: fields `name` (CharField, unique), `created_at`.
   - Add `TeacherSubjectGrade` model: fields `teacher` (FK to Teacher), `subject` (FK to Subject), `school_grade` (FK to SchoolGrade). Add a `unique_together = ['teacher', 'subject', 'school_grade']` constraint.
   - **Note:** Do NOT alter the existing `subject` CharField on the `Teacher` model.
2. **Admin UI Views & Templates:**
   - Create CRUD views for `SchoolGrade` and `Subject` in `admin_portal/views.py`.
   - Create simple list, add, edit templates for them.
   - Add a UI section on the teacher edit page to manage their `TeacherSubjectGrade` links.
3. **Sidebar:** Update the admin sidebar navigation in `templates/base.html` (or sidebar template) to include links to "المراحل والمواد" (Grades & Subjects).
4. **Testing:** Run `python manage.py makemigrations` and `migrate`. Run tests.

---

## Phase 3 — Student Model Updates

**Goal**: Add `student_type`, `school_grade` FK, and 24 payment fields to the Student model.

**Steps to Implement:**
1. **Models:** In `core/models.py`, update `Student`:
   - Add `StudentType` TextChoices ('regular', 'course').
   - Add `student_type` CharField (choices=StudentType.choices, default='regular').
   - Add `school_grade` FK to `SchoolGrade` (null=True, blank=True, on_delete=SET_NULL).
   - Add `PaymentStatus` TextChoices ('not_paid', 'partial', 'paid').
   - Add 12 payment status fields (`payment_status_jan` through `payment_status_dec`, choices=PaymentStatus, default='not_paid').
   - Add 12 payment note fields (`payment_note_jan` through `payment_note_dec`, TextField, blank=True, default='').
   - **Note:** Do NOT alter the existing `grade` CharField.
2. **Forms:** Update `StudentForm` in `admin_portal/forms.py` to include `student_type` and `school_grade`. (Payment fields will have a separate dedicated UI).
3. **Admin UI:** Update the student list view and template to add filtering by `student_type` and `school_grade`.
4. **Testing:** Run migrations and verify existing students default to 'regular' and 'not_paid'.

---

## Phase 4 — Teacher Model Updates

**Goal**: Add `teacher_type` choice and `description` to Teacher.

**Steps to Implement:**
1. **Models:** In `core/models.py`, update `Teacher`:
   - Add `TeacherType` TextChoices ('teacher', 'course').
   - Add `teacher_type` CharField (choices=TeacherType.choices, default='teacher').
   - Add `description` TextField (blank=True, default='').
2. **Forms:** Update `TeacherForm` in `admin_portal/forms.py` to include these fields.
3. **UI Filters:** 
   - Add `teacher_type` filtering to the teacher list page in the admin portal.
   - Add `teacher_type` filtering to the supervisor dashboard.
4. **Testing:** Run migrations and verify filters.

---

## Phase 5 — Assistant Teacher Role & Portal

**Goal**: Add an `ASSISTANT` user role with a dedicated portal for selecting linked teachers.

**Steps to Implement:**
1. **Models:** In `core/models.py`:
   - Add `ASSISTANT` to `User.Role` TextChoices.
   - Add an `@property def is_assistant(self)` to the `User` model.
   - Create `AssistantTeacherLink` model: fields `user` (FK to User), `teacher` (FK to Teacher), `unique_together = ['user', 'teacher']`.
2. **New App:** 
   - Create a new Django app `assistant_portal`. Add it to `INSTALLED_APPS`.
   - Create `views.py` with `dashboard`, `select_teacher` (sets `assistant_teacher_id` in session), and `deselect_teacher` views.
   - The dashboard should only list teachers linked to the current user via `AssistantTeacherLink`.
   - Create URLs and templates for this portal (similar to the supervisor portal).
3. **Access Control:** 
   - In `teacher_portal/views.py`, update the `teacher_required` decorator to allow `request.user.is_assistant` if they have an `assistant_teacher_id` in session.
   - Update `get_acting_teacher` to return the linked teacher for assistants (verifying the link exists to prevent session tampering).
   - In `core/views.py`, update `dashboard_redirect` to route assistants to their new portal.
4. **Admin UI:** Add CRUD pages for assistants in the admin portal, including UI to link/unlink them from teachers.

---

## Phase 6 — Admin UI Wiring

**Goal**: Finalize all admin portal UI for the new features.

**Steps to Implement:**
1. Update `templates/base.html` (or the layout containing the sidebar) to include links to the Assistant Management pages.
2. Ensure all forms and views created in Phases 2 and 5 are fully functional and accessible from the admin sidebar.
3. Test all CRUD operations.

---

## Phase 7 — Payment Management & Export

**Goal**: Dedicated payment page per student + global payments overview.

**Steps to Implement:**
1. **Student Payment UI:** 
   - Create a view and template: `/portal/admin/students/<id>/payments/`.
   - Display a 12-month grid. Each month has status buttons ( لم يدفع / دفع جزئي / تم الدفع ) and a note textarea.
   - Link this page from the student detail page.
2. **Global Payments UI:** 
   - Create a view and template: `/portal/admin/payments/`.
   - Add summary stats (paid/partial/unpaid counts).
   - Add a table filtering students by month, status, teacher, and student type.
3. **Excel Export:** Add export functionality to the global payments view to download the filtered dataset.
4. **Testing:** Toggle payment statuses, verify filtering, and verify the excel export output.
