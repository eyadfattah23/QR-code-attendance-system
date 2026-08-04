# QR Code Attendance System

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![Django](https://img.shields.io/badge/Django-6.0+-092E20.svg?logo=django)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Ready-336791.svg?logo=postgresql)
![License](https://img.shields.io/badge/License-Proprietary-red.svg)

A robust, localized (Arabic RTL), Django-based attendance system utilizing QR code scanning. Designed specifically for educational institutions to streamline the daily check-in process, manage substitute teachers, and provide a seamless experience for administrators, supervisors, and teachers.

---

## Features

- **Rapid QR Code Check-in**: Instantly record attendance using unique QR code cards.
- **Batch Scanning**: Scan and process multiple student cards simultaneously to eliminate bottlenecks.
- **Dynamic Portals**: Dedicated workspaces tailored for Admins, Supervisors, and Teachers.
- **Substitute Teacher Handling**: Intelligently track teacher absences and automatically reassign students for the day.
- **Daily Student Evaluation**: Teachers can attach a daily photo, assign a performance rating (1-10), and leave daily behavioral notes for each student.
- **QR Card Generator**: Programmatically generate printable PDF ID cards with customizable grid layouts.
- **Rich Reporting & Exporting**: Export attendance data, substitute notes, and student histories to Excel (`.xlsx`).
- **Fully Localized**: Complete Arabic Language support with right-to-left (RTL) interface design.

---

## Tech Stack

- **Backend Architecture**: Django 6.0+ & Django REST Framework
- **Frontend Interactivity**: Django Templates, Vanilla JavaScript, & HTMX
- **Database Engine**: SQLite (Development) / PostgreSQL (Production)
- **PDF Engine**: ReportLab
- **Data Export**: OpenPyXL

---

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL (for production environments)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "QR code attendance system"
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your local settings (Database, Secret Key, etc.)
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Seed Initial Admin**
   ```bash
   python manage.py seed_admin
   # Default credentials: username=admin, password=admin123
   ```

7. **Launch the development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the application**
   - Application URL: [http://localhost:8000/](http://localhost:8000/)
   - Django Admin: [http://localhost:8000/admin/](http://localhost:8000/admin/)

---

## Project Structure

```text
qr_attendance/
├── manage.py
├── requirements.txt
├── pytest.ini
├── .env.example
│
├── qr_attendance/              # Core Django project settings
│
├── core/                       # Core models (Users, Students, Teachers)
├── attendance/                 # Core attendance logic & daily photos
├── admin_portal/               # Admin dashboard & management views
├── supervisor_portal/          # Supervisor dashboard & acting tools
├── teacher_portal/             # Teacher attendance tracking & notes
├── qr_generator/               # PDF Generation for QR Codes
│
├── templates/                  # Modular HTML templates
├── static/                     # CSS, Fonts, and JavaScript assets
├── media/                      # Uploaded files (Student Photos)
└── docs/                       # Extensive System Documentation
```

---

## User Roles & Permissions

- **Admin**: Full system access. Can manage students, teachers, view all records, edit attendance notes, and export system-wide data.
- **Supervisor**: Oversight role. Can view all teachers, filter them by subject and attendance metrics, and act on behalf of any teacher to assist them.
- **Teacher**: Restricted view. Can only access their linked students (and daily assigned substitute students), upload daily photos, and view their class's specific attendance history.

---

## Configuration Variables

Key environment variables required for deployment (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django cryptographic secret key | - |
| `DB_NAME` | Database name | `qr_attendance` |
| `DB_USER` | Database user | `qr_attendance` |
| `DB_PASSWORD` | Database password | - |
| `DB_HOST` | Database host | `localhost` |
| `TIME_ZONE` | Application timezone | `Africa/Cairo` |
| `ALLOWED_HOSTS` | Allowed hosts (comma-separated) | `localhost, 127.0.0.1` |

---

## Running Tests

This project enforces a strict testing methodology utilizing `pytest`.

```bash
# Execute the full test suite
pytest

# Execute with coverage report
pytest --cov

# Execute tests for a specific module
pytest core/tests/
```

---

## QR Code Card Generation Layouts

The `qr_generator` application can format PDF outputs into standard grid layouts for printing:

| Cards/Page | Grid Layout | Approx. Card Size | Best For |
|------------|-------------|-------------------|----------|
| **1** | 1×1 | 190×277 mm | Full Page Display |
| **4** | 2×2 | 95×138 mm | Badges / Large tags |
| **8** | 2×4 | 95×69 mm | **Standard ID Card** |
| **10** | 2×5 | 95×55 mm | Standard Business Card |
| **12** | 3×4 | 63×69 mm | Small sticky labels |

---

## Documentation

For deep dives into the system architecture and deployment guidelines, refer to the `docs/` directory:
- [Authentication System](docs/AUTHENTICATION.md)
- [Attendance Logic & Schema](docs/ATTENDANCE.md)
- [Production Deployment](docs/deployment.md)

---

## License

This software is developed for internal use by **Redwan Oasis**. Proprietary and confidential.
