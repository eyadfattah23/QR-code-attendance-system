# نظام الحضور والمسح | Attendance & Scanning System

## نظرة عامة | Overview

نظام المسح يدعم نمطي من التسجيل:

### 📊 **Scan Station** (Admin Only)
- **URL**: `/scan/`
- **Permission**: Admin only
- **Features**: 
  - Scan ANY student in the system
  - Batch processing (multiple codes at once)
  - Access QR codes, student codes, or national IDs
  - Dedicated full-screen interface

### 👨‍🏫 **Teacher Dashboard Scan** (Teacher Only)
- **URL**: `/portal/teacher/`
- **Permission**: Teachers only, integrated in dashboard
- **Features**:
  - Scan ONLY students linked to that teacher
  - Inline form in their dashboard
  - Results displayed as success/warning messages
  - Automatic validation of student-teacher relationship

---

## الأدوار والأذونات | Permissions

### Admin Role
- ✅ Can access scan station: `/scan/` (full-screen dedicated interface)
- ✅ Can submit attendance scans for ANY student
- ✅ Cannot access teacher dashboard scan form

### Teacher Role
- ✅ Can access teacher dashboard: `/portal/teacher/`
- ✅ Can scan ONLY their linked students from dashboard form
- ✅ CANNOT access admin scan station `/scan/` (blocked by decorator)

---

## Implementation Architecture

### Scan Station (Admin Only)
**File**: [attendance/views.py](../attendance/views.py)

```python
@admin_required
@require_http_methods(["GET", "POST"])
def station_view(request):
    """Admin-only full-screen scan interface."""
    # GET: Display scan form + recent scans
    # POST: Process batch of scanned codes for ANY student
```

**Decorator**: 
```python
def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin:
            messages.error(request, 'ليس لديك صلاحية الوصول إلى محطة المسح')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
```

**Route**: [attendance/urls.py](../attendance/urls.py)
```python
path('', views.station_view, name='station')
# URL: /scan/
```

### Teacher Dashboard Scan (Teachers Only)
**File**: [teacher_portal/views.py](../teacher_portal/views.py)

```python
@teacher_required
@require_http_methods(["POST"])
def teacher_scan(request):
    """Scan students linked to the current teacher."""
    # Process scanned codes
    # Only allows scanning students in:
    #   StudentTeacherLink.objects.filter(teacher=current_teacher)
    # Validates each student is linked before creating record
```

**Route**: [teacher_portal/urls.py](../teacher_portal/urls.py)
```python
path('scan/', views.teacher_scan, name='scan')
# URL: /portal/teacher/scan/ (POST only)
```

---

## وظائف المسح | Scanning Logic

### Admin Scan (Full Access)
In [attendance/views.py](../attendance/views.py) - `station_view()`:

```python
for raw_code in codes:
    # Try UUID lookup → Student.objects.filter(id=code_uuid)
    # Try Student Code → Student.objects.filter(student_code__iexact=code)
    # Try National ID → Student.objects.filter(national_id__iexact=code)
    
    # Create attendance record for ANY found student
```

### Teacher Scan (Restricted Access)
In [teacher_portal/views.py](../teacher_portal/views.py) - `teacher_scan()`:

```python
for raw_code in codes:
    # Get teacher's linked students
    linked_student_ids = StudentTeacherLink.objects.filter(
        teacher=teacher
    ).values_list('student_id', flat=True)
    
    # Try UUID lookup → filter by id AND id__in linked_student_ids
    # Try Student Code → filter by student_code AND id__in linked_student_ids
    # Try National ID → filter by national_id AND id__in linked_student_ids
    
    # Only create record if student is linked to teacher
```

---

## نموذج البيانات | Data Model

### StudentAttendanceRecord
```python
{
    'id': UUID,
    'student': FK(Student),
    'date': Date,
    'check_in_time': DateTime,
    'recorded_by': FK(User),  # Who scanned (admin or teacher)
    'original_teacher': FK(Teacher),
    'assigned_teacher': FK(Teacher),
    'substitute_note': str,
    'daily_photo': ImageField (optional),
    'rating': int (1-10)
}
```

**Unique Constraint**: `(student, date)` - One record per student per day

---

## واجهات المستخدم | User Interfaces

### Admin Scan Station (`/scan/`)
```
┌─────────────────────────────────────────┐
│  محطة المسح - Scan Station             │
├─────────────────────────────────────────┤
│                                         │
│  [Textarea: Enter/Paste Codes]         │
│  [Submit] [Clear]                       │
│                                         │
│  ─────────────────────────────────────  │
│  Results:                              │
│  ✓ Student 1 - Success                 │
│  ⚠ Student 2 - Already scanned         │
│  ✗ Unknown code: ABC123                │
│                                         │
│  Recent Scans (last 10)                │
│  ...                                   │
│                                         │
└─────────────────────────────────────────┘
```

- Full-screen interface
- Batch processing
- Sound feedback on completion
- Recent scans list

### Teacher Dashboard (`/portal/teacher/`)
```
┌───────────────────────────────────┐
│ لوحة المعلم - Teacher Dashboard  │
├───────────────────────────────────┤
│                                   │
│  [Scan Section]                  │
│  [Textarea: Scan Linked Students]│
│  [Submit]                         │
│                                   │
│  Messages:                        │
│  ✓ Student scanned               │
│  ✗ Student not linked to you     │
│                                   │
│  Student List:                   │
│  - Name | Status | Check-in time │
│  ...                             │
│                                   │
└───────────────────────────────────┘
```

- Inline form in dashboard
- Messages show success/error
- Only shows linked students in list
- Easy quick scanning during class

---

## الاختبارات | Testing

### Test Coverage

Located in: [attendance/tests/test_views.py](../attendance/tests/test_views.py)

**13 Test Cases**:

#### Scan Station Permission Tests (Admin Only)
- ✅ `test_scan_page_requires_login` - Unauthenticated denied
- ✅ `test_admin_can_access_scan_station` - Admin access granted
- ✅ `test_teacher_cannot_access_scan_station` - Teacher access blocked

#### Admin Scan Tests
- ✅ `test_admin_can_scan_any_student` - Scan any student in system
- ✅ `test_admin_scan_by_student_code` - Lookup by code works

#### Teacher Scan Tests (Linked Students Only)
- ✅ `test_teacher_can_scan_linked_students_by_uuid` - UUID lookup for linked student
- ✅ `test_teacher_can_scan_linked_students_by_code` - Code lookup for linked student
- ✅ `test_teacher_can_scan_linked_students_by_national_id` - National ID lookup
- ✅ `test_teacher_cannot_scan_unlinked_students` - Blocks unlinked students
- ✅ `test_teacher_can_scan_multiple_linked_students` - Batch scanning
- ✅ `test_teacher_scan_duplicate_prevention` - Prevents duplicate records
- ✅ `test_teacher_scan_recorded_by_teacher` - Records teacher as recorded_by
- ✅ `test_teacher_cannot_access_endpoint_if_not_logged_in` - Auth required

### Running Tests

```bash
# Run only attendance tests
python manage.py test attendance.tests.test_views -v 2

# Run all core and attendance tests
python manage.py test core.tests attendance.tests

# Results: All 70 tests passing ✅
```

---

## التنقل | Navigation

### Navigation Bar (`templates/base.html`)

```html
<!-- Admin Only -->
{% if user.is_admin %}
  <a href="/portal/admin/">لوحة المدير (Admin Dashboard)</a>
  <a href="/scan/">محطة المسح (Scan Station)</a> <!-- Admin exclusive -->
{% elif user.is_teacher %}
  <a href="/portal/teacher/">لوحة المعلم (Teacher Dashboard)</a>
  <!-- Teachers access scan form in dashboard, NOT scan station link -->
{% endif %}
```

**Key Difference**:
- **Admin**: Gets navigation link to `/scan/` (dedicated scan station)
- **Teacher**: NO scan link in nav; uses form in their dashboard instead

---

## معالجة الأخطاء | Error Handling

### Scan Station (Admin)
**Errors handled**:
- ✅ Empty code input
- ✅ Invalid UUID format → falls back to code/national_id lookup
- ✅ Code not found → Error message
- ✅ Student already scanned today → Warning message

### Teacher Scan (Dashboard)
**Errors handled**:
- ✅ Student not linked to teacher → Error message displayed
- ✅ Invalid scan code → Error message
- ✅ Duplicate scan → Warning message
- ✅ Teacher not linked to User account → Error message

**Messages displayed as**:
```python
messages.success(request, "Success message")   # Green
messages.warning(request, "Already exists")    # Yellow
messages.error(request, "Not linked to you")   # Red
```

---

## مثال استخدام | Usage Examples

### Scenario 1: Admin Scans Multiple Students

```
1. Admin goes to /scan/
2. Enters codes:
   550e8400-e29b-41d4-a716-446655440000
   STU-2024-001
   12345678901234
3. Clicks Submit
4. System shows:
   ✓ Ahmed Mohamed - Success
   ✓ Sara Ali - Success
   ✓ Mohamed Hassan - Success
```

### Scenario 2: Teacher Scans Only Linked Students

```
1. Teacher opens /portal/teacher/
2. Sees inline scan form
3. Enters student codes from their class:
   STU001
   STU002
4. Clicks Submit
5. System shows:
   ✓ Linked Student 1 - Success
   ✓ Linked Student 2 - Success
   
6. Teacher tries scanning a student from another class:
   STU999
7. System shows:
   ✗ Error: Student not linked to you
```

---

## ملاحظات التطوير | Developer Notes

### Key Files

| File | Purpose | Status |
|------|---------|--------|
| [attendance/views.py](../attendance/views.py) | Scan station logic + admin_required decorator | ✅ Complete |
| [teacher_portal/views.py](../teacher_portal/views.py) | Teacher scan endpoint + validation | ✅ Complete |
| [attendance/urls.py](../attendance/urls.py) | Route `/scan/` to station_view | ✅ Complete |
| [teacher_portal/urls.py](../teacher_portal/urls.py) | Route `/portal/teacher/scan/` to teacher_scan | ✅ Complete |
| [templates/base.html](../templates/base.html) | Navigation links (admin → /scan/, teacher → dashboard) | ✅ Complete |
| [templates/teacher_portal/dashboard.html](../templates/teacher_portal/dashboard.html) | Teacher scan form POSTs to teacher_portal:scan | ✅ Complete |
| [attendance/tests/test_views.py](../attendance/tests/test_views.py) | 13 comprehensive tests | ✅ Complete |

### Adding New Scan Input Format

To support a new lookup method (e.g., barcode), modify both scan endpoints:

**In `attendance/views.py` - `station_view()`**:
```python
if student is None:
    student = Student.objects.filter(barcode__iexact=lookup).first()
```

**In `teacher_portal/views.py` - `teacher_scan()`**:
```python
if student is None:
    student = Student.objects.filter(
        barcode__iexact=lookup,
        id__in=linked_student_ids  # IMPORTANT: Filter by linked students
    ).first()
```

### Changing Permission Levels

**To allow both admins AND teachers in scan station**:
```python
# Change in attendance/views.py
def admin_or_teacher_required(view_func):  # New decorator
    ...
    if not (request.user.is_admin or request.user.is_teacher):
```

Then update tests and navigation accordingly.

---

## الأسئلة الشائعة | FAQ

### Q: Can a teacher scan students from another teacher's class?
**A**: No. Teachers can only scan students in their `StudentTeacherLink` records. If a student is linked to another teacher, the scan will be rejected with "Student not linked to you" message.

### Q: What if a teacher tries to access `/scan/`?
**A**: The `@admin_required` decorator blocks access and redirects them to dashboard with error message "ليس لديك صلاحية الوصول إلى محطة المسح"

### Q: Can a teacher scan the same student twice on the same day?
**A**: The system will create the record on first scan and show "Already recorded" warning on second scan. No duplicate record is created.

### Q: Who is recorded as "recorded_by" when a teacher scans?
**A**: The teacher user is recorded. If admin scans, admin is recorded. This allows tracking who entered the attendance.

### Q: Can teachers batch scan multiple students?
**A**: Yes! Teachers can use Shift+Enter for newlines in the textarea, paste multiple student codes, and submit once.

---

## URL Mappings

| URL | Method | Permission | Description |
|-----|--------|-----------|-------------|
| `/scan/` | GET | Admin | Display admin scan station |
| `/scan/` | POST | Admin | Process batch scans (any student) |
| `/portal/teacher/` | GET | Teacher | Display teacher dashboard (has scan form) |
| `/portal/teacher/scan/` | POST | Teacher | Process scans (only linked students) |

---

## Related Documentation

- [AUTHENTICATION.md](AUTHENTICATION.md) - User roles and authentication
- [plan.md](../plan.md) - Project implementation plan
