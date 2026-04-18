# QR Code Attendance System

A local Django-based attendance system with QR code scanning, designed for educational institutions.

## Features

- **QR Code Check-in**: Students and teachers check in by scanning their QR code cards
- **Batch Scanning**: Scan multiple cards at once, submit in batches
- **Admin Portal**: Manage students, teachers, view attendance records, export to Excel
- **Teacher Portal**: View students, upload daily photos, see attendance history
- **Substitute Teacher Handling**: Track when teachers are absent and students are reassigned
- **QR Card Generation**: Generate printable QR code cards as PDF

## Tech Stack

- **Backend**: Django 6.0+ with Django REST Framework
- **Database**: SQLite (development) / PostgreSQL (production)
- **Frontend**: Django Templates + HTMX
- **PDF Generation**: ReportLab
- **Excel Export**: openpyxl

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL (for production)

### Development Setup

1. **Clone the repository**
   ```bash
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

4. **Copy environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create admin user**
   ```bash
   python manage.py seed_admin
   # Default: username=admin, password=admin123
   ```

7. **Run development server**
   ```bash
   python manage.py runserver
   ```

8. **Access the application**
   - Admin: http://localhost:8000/admin/
   - Application: http://localhost:8000/

### Production Setup

See [docs/deployment.md](docs/deployment.md) for detailed production deployment instructions.

## Project Structure

```
qr_attendance/
├── manage.py
├── requirements.txt
├── pytest.ini
├── .env.example
│
├── qr_attendance/              # Django project settings
│   ├── settings/
│   │   ├── base.py             # Shared settings
│   │   ├── development.py      # Development settings
│   │   └── production.py       # Production settings
│   ├── urls.py
│   └── wsgi.py
│
├── core/                       # Core models (User, Student, Teacher)
├── attendance/                 # Attendance records and photos
├── admin_portal/               # Admin-specific views
├── teacher_portal/             # Teacher-specific views
├── qr_generator/               # QR code generation
│
├── templates/                  # HTML templates
├── static/                     # Static files (CSS, JS)
├── media/                      # Uploaded files (photos)
└── docs/                       # Documentation
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific app tests
pytest core/tests/
```

## Configuration

Key environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | - |
| `DB_NAME` | Database name | `qr_attendance` |
| `DB_USER` | Database user | `qr_attendance` |
| `DB_PASSWORD` | Database password | - |
| `DB_HOST` | Database host | `localhost` |
| `TIME_ZONE` | Application timezone | `Africa/Cairo` |
| `ALLOWED_HOSTS` | Allowed hosts (comma-separated) | `localhost,127.0.0.1` |

## User Roles

- **Admin**: Full access - manage students/teachers, view all records, export data
- **Teacher**: View assigned students, upload daily photos, view attendance history

## License

This project is for internal use by [Organization Name].
