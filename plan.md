# Plan: QR Code Attendance System

A local Django-based attendance system with QR scanning, teacher photo uploads, and substitute teacher assignment.

## TL;DR

Build a Django web application on an Ubuntu server. A separate scanning PC with USB QR scanner sends batch check-ins to the server via WiFi. Three interfaces: Admin Portal (full control, reports), Teacher Portal (daily student table + history + photo upload), Scan Station (batch scanning page). One-month timeline is achievable.

---

## Architecture Overview

```
┌─────────────────────┐         WiFi/LAN         ┌─────────────────────┐
│   SCANNING PC       │ ─────────────────────►   │   UBUNTU SERVER     │
│   (any laptop/PC)   │                          │   (dedicated PC)    │
│                     │                          │                     │
│ [USB QR Scanner]    │                          │ [Django Backend]    │
│ [Browser - Scan     │                          │ [PostgreSQL]        │
│  Station Page]      │                          │ [Media Storage]     │
└─────────────────────┘                          └─────────────────────┘
                                                          ↑
                               WiFi/LAN                   │
        ┌─────────────────────────────────────────────────┤
        │                       │                         │
┌───────┴───────┐     ┌────────┴────────┐     ┌─────────┴─────────┐
│ Admin Device  │     │ Teacher Phone   │     │ Teacher Laptop    │
│ (laptop/PC)   │     │ (photo upload)  │     │ (view records)    │
│ Admin Portal  │     │ Teacher Portal  │     │ Teacher Portal    │
└───────────────┘     └─────────────────┘     └───────────────────┘
```

**Hardware Setup:**
- **Server PC**: Ubuntu Server 22.04 LTS, runs Django + PostgreSQL
- **Scanning PC**: Any laptop/PC with browser, connected to same network
- **USB QR Scanner**: ~$30, plugs into scanning PC, acts as keyboard
- **Router**: Connects all devices on campus LAN
- **Access**: Via server IP (e.g., `http://192.168.1.100`)

**Tech Stack:**
- Backend: Django 5.x + Django REST Framework
- Database: PostgreSQL 15 (handles 2000 students easily, better than SQLite for concurrent access)
- Frontend: Django Templates + HTMX (fast dev, no separate frontend build)
- CSS: Tailwind CSS or Bootstrap 5 (responsive for teacher mobile)
- PDF Generation: ReportLab (QR cards)
- QR Codes: `qrcode` Python library
- Excel Export: `openpyxl`
- Photo Storage: Local filesystem with Django media handling

---

## Database Schema

### Core Models

**User** (Django's built-in, extended)
- role: enum (admin, teacher)
- phone: optional

**Student**
- id: UUID (used in QR code)
- national_id: string (unique)
- full_name: string
- grade/class: string (optional)
- created_at, updated_at

**Teacher** (extends User)
- teacher_id: UUID (used in QR code)
- full_name: string
- subject: string (optional)

**StudentTeacherLink**
- student: FK → Student
- teacher: FK → Teacher
- is_primary: boolean (for display purposes)
- created_at

**AttendanceRecord**
- id: UUID
- person_type: enum (student, teacher)
- student: FK → Student (nullable)
- teacher: FK → Teacher (nullable)
- date: date
- check_in_time: datetime
- recorded_by: FK → User (admin who was logged in)
- assigned_teacher: FK → Teacher (can differ from default on substitute days)
- substitute_note: string (optional, e.g., "Original teacher absent")
- created_at

**DailyPhoto**
- student: FK → Student
- teacher: FK → Teacher (who uploaded)
- date: date
- photo: ImageField
- uploaded_at: datetime
- UNIQUE(student, date)

---

## Phases & Steps

### Phase 1: Foundation (Days 1-5)

1. **Project setup** — Django project, PostgreSQL, environment config, Git repo
2. **User authentication** — Django auth with role-based permissions (admin/teacher)
3. **Core models** — Student, Teacher, StudentTeacherLink, migrations
4. **Admin seeding** — Management command to create initial admin user
5. **Basic templates** — Base layout, login page, dashboard skeleton

*Deliverable: Login works, database ready*

### Phase 2: Scan Station (Days 6-10)

6. **Scan page UI** — Full-screen page with:
   - Large textarea for accumulating scanned codes
   - "Submit Batch" button (or Enter key)
   - Results panel showing processed records
   - Clear button for next batch
7. **Batch processing endpoint** — POST endpoint that:
   - Receives list of scanned IDs (newline-separated)
   - For each ID: identify student/teacher, create AttendanceRecord if not exists today
   - Return detailed results per ID (success, already scanned, not found)
8. **Results display** — Show after batch submit:
   - ✓ "Ahmed Mohamed - Checked in at 8:15 AM"
   - ⚠ "Sara Ali - Already checked in at 7:45 AM"  
   - ✗ "Unknown code: ABC123"
9. **Sound feedback** — Success sound for batch complete, error beep if any failures
10. **Scan history panel** — Show today's total check-ins, last few successful scans

*Deliverable: Functional batch check-in station*

### Phase 3: Admin Portal (Days 11-17)

11. **Dashboard home** — Today's attendance summary (students: X/2000, teachers: X/200)
12. **Student management** — CRUD, bulk import from Excel, search/filter
13. **Teacher management** — CRUD, link to User account
14. **Student-Teacher linking UI** — Multi-select interface to assign students to teachers (many-to-many)
15. **All students browser** — Searchable/filterable table of ALL students
    - Click student → full attendance history with photos (same as teacher view but for ALL students)
16. **Attendance records view** — Filterable table (date range, teacher, student, grade)
17. **Excel export** — Download filtered records as .xlsx
18. **QR code generation** — Generate QR codes (just code, no fancy design), bulk PDF export (configurable cards per page: 8, 10, 12)
19. **Teacher absence handling UI** — Mark teacher absent, assign substitute to their students' records for the day

*Deliverable: Full admin functionality*

### Phase 4: Teacher Portal (Days 18-23)

19. **Teacher dashboard** — Today's summary (X of Y students attended)
20. **Daily student table** — Shows ALL linked students with columns:
    - Student name
    - Status (✓ Attended / ✗ Absent)
    - Check-in time (if attended)
    - Photo status (uploaded / not uploaded)
    - Action: Upload photo button
21. **Student history page** — Click student name → full attendance history:
    - List of all attendance records (date, check-in time, assigned teacher)
    - Photos displayed inline for each day (if uploaded)
    - Scrollable, most recent first
22. **Photo upload flow** — 
    - Mobile-optimized camera capture or file upload
    - Confirm before replacing existing photo
    - Compress images (max 1MB)
23. **Absent teacher indicator** — On student records where teacher was substituted:
    - Red banner: "Original teacher [X] was absent"
    - Shows substitute teacher name

*Deliverable: Teacher can view all students, see history, upload photos*

### Phase 5: Testing & Documentation (Days 24-28)

24. **Unit tests** — Test models, services, and utility functions
    - Student/Teacher/AttendanceRecord model tests
    - QR generation tests
    - Batch scan processing logic tests
    - Excel export tests
25. **Integration tests** — Test API endpoints and views
    - Scan station batch submission
    - Photo upload flow
    - Authentication and authorization
    - Student-teacher linking
26. **End-to-end tests** — Full user flows with test data
    - Admin creates student → generates QR → scans → views record
    - Teacher views students → uploads photo → views history
    - Substitute assignment flow
27. **Test data generation** — Management command to seed 100+ test records
28. **Code documentation** — Docstrings, type hints, inline comments

*Deliverable: Test coverage >80%, documented codebase*

### Phase 6: Deployment & User Docs (Days 29-30)

29. **Deployment documentation:**
    - `docs/deployment.md` — Ubuntu Server setup step-by-step
    - `docs/configuration.md` — Environment variables, settings
    - `docs/backup.md` — Backup and restore procedures
    - `docs/troubleshooting.md` — Common issues and solutions
30. **User documentation:**
    - `docs/admin-guide.md` — Full admin portal walkthrough
    - `docs/teacher-guide.md` — Teacher portal usage guide
    - `docs/scanning-guide.md` — How to use the scan station
    - **Backup script** — Automated daily PostgreSQL backup

*Deliverable: Production-ready system with full documentation*

---

## Relevant Files (to be created)

```
qr_attendance/
├── manage.py
├── requirements.txt
├── pytest.ini
├── .env.example
├── README.md
│
├── qr_attendance/              # Django project settings
│   ├── settings/
│   │   ├── base.py             # Shared settings
│   │   ├── development.py      # Dev settings
│   │   └── production.py       # Production settings
│   ├── urls.py
│   └── wsgi.py
│
├── core/                       # Shared models, utils
│   ├── models.py               # Student, Teacher, StudentTeacherLink
│   ├── tests/
│   │   ├── test_models.py
│   │   └── test_services.py
│   └── management/commands/
│       ├── seed_admin.py
│       ├── seed_test_data.py   # Generate test data
│       └── import_students.py
│
├── attendance/                 # Attendance logic
│   ├── models.py               # AttendanceRecord, DailyPhoto
│   ├── views.py                # Scan endpoint, record views
│   ├── services.py             # Business logic
│   └── tests/
│       ├── test_views.py
│       ├── test_services.py
│       └── test_batch_scan.py
│
├── admin_portal/               # Admin-specific views
│   ├── views.py
│   ├── exports.py              # Excel export logic
│   └── tests/
│       └── test_exports.py
│
├── teacher_portal/             # Teacher-specific views
│   ├── views.py
│   └── tests/
│       └── test_views.py
│
├── qr_generator/               # QR code generation
│   ├── generator.py
│   ├── pdf_export.py
│   └── tests/
│       └── test_generator.py
│
├── templates/
│   ├── base.html
│   ├── scan/station.html
│   ├── admin/...
│   └── teacher/...
│
├── static/
│   ├── css/
│   └── js/scan.js              # Batch scan handling
│
├── media/                      # Uploaded photos
│
└── docs/
    ├── deployment.md           # Ubuntu Server setup
    ├── configuration.md        # Environment variables
    ├── backup.md               # Backup procedures
    ├── troubleshooting.md      # Common issues
    ├── admin-guide.md          # Admin portal guide
    ├── teacher-guide.md        # Teacher portal guide
    └── scanning-guide.md       # Scan station usage
```

---

## Verification Steps

1. **Batch scan flow** — Scan 5 test QR codes, press Enter, verify all records created
2. **Duplicate in batch** — Include same QR twice in batch, verify appropriate warnings
3. **Same-day duplicate** — Scan student who already checked in, verify "already scanned" message
4. **Teacher daily table** — Login as teacher, verify ALL students shown (attended + absent)
5. **Student history (teacher)** — Click student → see full history with photos
6. **Student history (admin)** — Same feature but accessible for ANY student
7. **Excel export** — Filter records by date range, export, verify data integrity
8. **QR PDF generation** — Generate PDF with 10 student cards (simple QR codes), verify scannable
9. **Photo upload mobile** — Upload from phone browser, verify saved and linked to correct day
10. **Photo replacement** — Upload second photo same student/day, verify confirmation prompt
11. **Substitute assignment** — Mark teacher absent, reassign student, verify red indicator appears
12. **Cross-device access** — Access from multiple devices simultaneously

### Test Coverage Targets

13. **Unit tests pass** — Run `pytest` with all tests passing
14. **Coverage report** — `pytest --cov` shows >80% coverage
15. **Model tests** — All model methods and constraints tested
16. **View tests** — All endpoints return correct status codes and data
17. **Permission tests** — Verify teachers can't access admin routes and vice versa

### Documentation Verification

18. **Deployment doc test** — Follow `docs/deployment.md` on fresh Ubuntu, system runs
19. **Admin guide review** — Non-technical person can follow admin guide
20. **Teacher guide review** — Teacher can follow guide on mobile phone

---

## Key Decisions & Scope

**Included:**
- Batch QR scanning (flexible: 1, 10, or all at once)
- Separate scanning PC → server architecture
- Admin portal with full CRUD, filters, Excel export
- Teacher portal with daily ALL-students table + individual student history
- Student history view with photos (for teachers: their students; for admins: all students)
- Student-teacher many-to-many links
- Substitute teacher assignment per attendance record
- Simple QR card PDF generation (just QR code, no fancy design)
- Local-only deployment
- Single scanning station

**Explicitly Excluded:**
- Late arrival tracking (just check-in time recorded)
- Professional ID card design (just QR codes)
- Student self-service portal
- Automated notifications (email/SMS)
- Cloud backup sync
- Multi-campus support
- Multiple scan stations

**Technical Decisions:**
- PostgreSQL over SQLite for concurrent access at scale
- HTMX over React/Vue for faster development
- USB scanner on separate PC, connects via WiFi to server
- Local media storage

---

## Suggested Improvements (Optional, Post-MVP)

1. **Attendance reports** — Weekly/monthly PDF summary per teacher
2. **Audit log** — Track who made changes to records
3. **Data retention policy** — Auto-archive records older than X years
4. **Backup automation** — Scheduled daily backups with retention

---

## Hardware Requirements

**Ubuntu Server PC:**
- CPU: Any modern dual-core
- RAM: 8GB minimum (16GB preferred)
- Storage: 256GB SSD (photos will grow ~50GB/year at full usage)
- Ubuntu Server 22.04 LTS

**Scanning PC:** 
- Any laptop/PC with browser (can be old hardware)
- Connected to same WiFi/LAN as server

**USB QR Scanner:** 
- Netum NT-1228BL or similar (~$25-35)
- Plug-and-play, acts as keyboard
- Scans into any text field

---

## Timeline Risk Assessment

**Tight areas:**
- Teacher portal photo upload (mobile browser quirks)
- PDF generation styling
- Testing at scale

**Mitigations:**
- Start with simple photo upload, polish later
- Use proven PDF libraries
- Generate test data early

**If behind schedule:** Deprioritize teacher photo feature, add in week 5.
