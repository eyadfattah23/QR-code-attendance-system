#!/usr/bin/env python3
"""
import_students_from_excel.py
==============================
Reads student data from an Excel (.xlsx) file and upserts records into the
production PostgreSQL `students` table.

Match priority:
  1. student_code  (if present in the Excel row)
  2. national_id   (fallback)
  3. Neither found → INSERT new student

Usage
-----
  # Basic (reads DB credentials from .env in the project root):
  python scripts/import_students_from_excel.py students.xlsx

  # Override any value via environment variable:
  DB_HOST=myserver DB_PASSWORD=secret python scripts/import_students_from_excel.py students.xlsx

  # Dry-run (print what would happen, touch nothing):
  python scripts/import_students_from_excel.py students.xlsx --dry-run

  # Write the report to a file instead of stdout:
  python scripts/import_students_from_excel.py students.xlsx --report report.txt
"""

import argparse
import os
import sys
import uuid
from datetime import date, datetime
from pathlib import Path

# ── locate project root so we can load .env ──────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENV_FILE = PROJECT_ROOT / ".env"

# ── load .env manually (no external dep needed) ──────────────────────────────
def _load_env(path: Path) -> None:
    """Parse a simple KEY=VALUE .env file and inject into os.environ."""
    if not path.exists():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


_load_env(ENV_FILE)

# ── third-party imports (available in project venv) ──────────────────────────
try:
    import openpyxl
except ImportError:
    sys.exit("ERROR: openpyxl not found.  Run: pip install openpyxl")

try:
    import psycopg2
    from psycopg2 import sql as pgsql
except ImportError:
    sys.exit("ERROR: psycopg2 not found.  Run: pip install psycopg2-binary")

# ═════════════════════════════════════════════════════════════════════════════
# Configuration
# ═════════════════════════════════════════════════════════════════════════════

DB_CONFIG = {
    "host":     os.environ.get("DB_HOST",     "localhost"),
    "port":     int(os.environ.get("DB_PORT", "5432")),
    "dbname":   os.environ.get("DB_NAME",     "qr_attendance"),
    "user":     os.environ.get("DB_USER",     "qr_attendance"),
    "password": os.environ.get("DB_PASSWORD", ""),
}

# Excel column name → Student model field name mapping
COLUMN_MAP = {
    "full name":             "full_name",
    "national_id":           "national_id",
    "student_code":          "student_code",
    "grade":                 "grade",
    "gender":                "gender",
    "phone":                 "phone",
    "nickname":              "nickname",
    "date_of_birth":         "date_of_birth",
    "joining_date":          "joining_date",
    "hall_name":             "hall_name",
    "notes":                 "notes",
    "parent_phone":          "parent_phone",
    "parent_full_name":      "parent_full_name",
    "parent_qualification":  "parent_qualification",
    "parent_job":            "parent_job",
    "parent_calls_phone":    "parent_calls_phone",
    "parent_marital_status": "parent_marital_status",
    "parent_spouse_job":     "parent_spouse_job",
    "parent_address":        "parent_address",
    "child_pickup_person":   "child_pickup_person",
}

# Fields that are stored as plain text (possibly empty string, not NULL)
TEXT_FIELDS = {
    "full_name", "national_id", "student_code", "grade", "gender",
    "phone", "nickname", "hall_name", "notes",
    "parent_phone", "parent_full_name", "parent_qualification",
    "parent_job", "parent_calls_phone", "parent_marital_status",
    "parent_spouse_job", "parent_address", "child_pickup_person",
}

# Fields that are nullable (empty cell → NULL)
NULLABLE_FIELDS = {
    "phone", "parent_phone", "parent_calls_phone",
    "date_of_birth", "joining_date",
    "grade", "gender", "student_code",
}

# Fields that are dates
DATE_FIELDS = {"date_of_birth", "joining_date"}

# Valid gender values accepted from Excel
GENDER_MAP = {
    "m": "M", "male": "M", "ذكر": "M", "م": "M",
    "f": "F", "female": "F", "أنثى": "F", "أ": "F",
}

# Valid marital status values
MARITAL_STATUS_MAP = {
    "married":   "married",  "متزوج": "married",
    "divorced":  "divorced", "مطلق":  "divorced",
    "widowed":   "widowed",  "أرمل":  "widowed",
    "separated": "separated","منفصل": "separated",
}

# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def clean_phone(value) -> str | None:
    """Return a clean 11-digit phone string or None."""
    if value is None:
        return None
    s = str(value).strip().replace(" ", "").replace("-", "").replace("+2", "")
    if not s:
        return None
    # Sometimes Excel stores as float: '10xxxxxxxx.0'
    if s.endswith(".0"):
        s = s[:-2]
    return s if s.startswith("0") and len(s) == 11 else s


def clean_date(value) -> date | None:
    """Parse various date representations into a Python date, or None."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value if isinstance(value, date) else value.date()
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def clean_text(value, nullable: bool = False) -> str | None:
    """Strip and return text, converting to str.  Empty → '' or None."""
    if value is None:
        return None if nullable else ""
    s = str(value).strip()
    if not s:
        return None if nullable else ""
    return s


def parse_row(headers: list[str], row) -> dict:
    """Convert an openpyxl row into a clean field dict ready for DB insert."""
    raw = {headers[i]: cell.value for i, cell in enumerate(row) if i < len(headers)}
    data: dict = {}

    for col_name, field in COLUMN_MAP.items():
        val = raw.get(col_name)
        nullable = field in NULLABLE_FIELDS

        if field in DATE_FIELDS:
            data[field] = clean_date(val)

        elif field in ("phone", "parent_phone", "parent_calls_phone"):
            data[field] = clean_phone(val) if val else None

        elif field == "gender":
            cleaned = clean_text(val, nullable=True)
            if cleaned:
                data[field] = GENDER_MAP.get(cleaned.lower(), cleaned)
            else:
                data[field] = None

        elif field == "parent_marital_status":
            cleaned = clean_text(val, nullable=False)
            if cleaned:
                data[field] = MARITAL_STATUS_MAP.get(cleaned.lower(), "")
            else:
                data[field] = ""

        elif field in TEXT_FIELDS:
            data[field] = clean_text(val, nullable=nullable)

        else:
            data[field] = val

    return data


# ═════════════════════════════════════════════════════════════════════════════
# DB operations
# ═════════════════════════════════════════════════════════════════════════════

def find_existing_student(cur, student_code, national_id):
    """
    Return the existing student row (as dict) or None.
    Checks student_code first, then national_id.
    """
    if student_code:
        cur.execute(
            "SELECT id, student_code, national_id, full_name FROM students WHERE student_code = %s",
            (student_code,)
        )
        row = cur.fetchone()
        if row:
            return {"match_by": "student_code", **dict(zip(["id","student_code","national_id","full_name"], row))}

    if national_id:
        cur.execute(
            "SELECT id, student_code, national_id, full_name FROM students WHERE national_id = %s",
            (national_id,)
        )
        row = cur.fetchone()
        if row:
            return {"match_by": "national_id", **dict(zip(["id","student_code","national_id","full_name"], row))}

    return None


def insert_student(cur, data: dict) -> str:
    """INSERT a new student row and return the generated UUID."""
    new_id = str(uuid.uuid4())
    now = datetime.utcnow()

    fields = list(data.keys()) + ["id", "created_at", "updated_at"]
    values = list(data.values()) + [new_id, now, now]

    query = pgsql.SQL(
        "INSERT INTO students ({fields}) VALUES ({placeholders})"
    ).format(
        fields=pgsql.SQL(", ").join(map(pgsql.Identifier, fields)),
        placeholders=pgsql.SQL(", ").join(pgsql.Placeholder() * len(values)),
    )
    cur.execute(query, values)
    return new_id


def update_student(cur, student_id: str, data: dict, changed_fields: list[str]) -> None:
    """UPDATE only the fields that actually changed."""
    if not changed_fields:
        return

    now = datetime.utcnow()
    set_clause = pgsql.SQL(", ").join(
        pgsql.SQL("{} = %s").format(pgsql.Identifier(f)) for f in changed_fields
    )
    values = [data[f] for f in changed_fields] + [now, student_id]

    query = pgsql.SQL(
        "UPDATE students SET {set_clause}, updated_at = %s WHERE id = %s"
    ).format(set_clause=set_clause)
    cur.execute(query, values)


def get_current_values(cur, student_id: str, fields: list[str]) -> dict:
    """Fetch current values of specific fields for a student."""
    query = pgsql.SQL(
        "SELECT {fields} FROM students WHERE id = %s"
    ).format(
        fields=pgsql.SQL(", ").join(map(pgsql.Identifier, fields))
    )
    cur.execute(query, (student_id,))
    row = cur.fetchone()
    if not row:
        return {}
    return dict(zip(fields, row))


# ═════════════════════════════════════════════════════════════════════════════
# Report builder
# ═════════════════════════════════════════════════════════════════════════════

class Report:
    def __init__(self):
        self.inserted: list[dict] = []
        self.updated:  list[dict] = []
        self.skipped:  list[dict] = []   # no changes needed
        self.errors:   list[dict] = []

    def add_inserted(self, row_num, data, new_id):
        self.inserted.append({"row": row_num, "name": data.get("full_name"), "id": new_id,
                               "student_code": data.get("student_code"), "national_id": data.get("national_id")})

    def add_updated(self, row_num, data, existing, changed_fields):
        self.updated.append({"row": row_num, "name": data.get("full_name"),
                              "id": existing["id"], "match_by": existing["match_by"],
                              "student_code": data.get("student_code"), "national_id": data.get("national_id"),
                              "changed_fields": changed_fields})

    def add_skipped(self, row_num, data, existing):
        self.skipped.append({"row": row_num, "name": data.get("full_name"),
                              "id": existing["id"], "match_by": existing["match_by"]})

    def add_error(self, row_num, data, error):
        self.errors.append({"row": row_num, "name": data.get("full_name","?"),
                             "student_code": data.get("student_code"), "national_id": data.get("national_id"),
                             "error": str(error)})

    def render(self) -> str:
        lines = []
        sep = "=" * 70

        lines.append(sep)
        lines.append("  STUDENT IMPORT REPORT")
        lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(sep)
        lines.append(f"  ✅  Inserted : {len(self.inserted)}")
        lines.append(f"  ✏️   Updated  : {len(self.updated)}")
        lines.append(f"  ⏭️   Skipped  : {len(self.skipped)}  (no changes)")
        lines.append(f"  ❌  Errors   : {len(self.errors)}")
        lines.append(sep)

        if self.inserted:
            lines.append("\n── INSERTED (new students) " + "─" * 44)
            for r in self.inserted:
                lines.append(
                    f"  Row {r['row']:>4}  |  {r['name'] or '?':<40}  "
                    f"code={r['student_code']}  nid={r['national_id']}  uuid={r['id']}"
                )

        if self.updated:
            lines.append("\n── UPDATED (existing students) " + "─" * 40)
            for r in self.updated:
                lines.append(
                    f"  Row {r['row']:>4}  |  {r['name'] or '?':<40}  "
                    f"matched by={r['match_by']}  uuid={r['id']}"
                )
                lines.append(f"           Changed fields: {', '.join(r['changed_fields'])}")

        if self.skipped:
            lines.append("\n── SKIPPED (already up-to-date) " + "─" * 38)
            for r in self.skipped:
                lines.append(
                    f"  Row {r['row']:>4}  |  {r['name'] or '?':<40}  "
                    f"matched by={r['match_by']}  uuid={r['id']}"
                )

        if self.errors:
            lines.append("\n── ERRORS " + "─" * 60)
            for r in self.errors:
                lines.append(
                    f"  Row {r['row']:>4}  |  {r['name']:<40}  "
                    f"code={r['student_code']}  nid={r['national_id']}"
                )
                lines.append(f"           Error: {r['error']}")

        lines.append("\n" + sep)
        return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# Main logic
# ═════════════════════════════════════════════════════════════════════════════

def process_excel(excel_path: Path, dry_run: bool) -> Report:
    report = Report()

    # ── open workbook ────────────────────────────────────────────────────────
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows())
    if not rows:
        print("WARNING: Excel file is empty.")
        return report

    # ── read headers (first row) ─────────────────────────────────────────────
    raw_headers = [str(cell.value).strip().lower() if cell.value else "" for cell in rows[0]]
    print(f"Detected columns: {raw_headers}")

    # validate that we have the minimum required columns
    required = {"full name", "national_id"}
    missing = required - set(raw_headers)
    if missing:
        sys.exit(f"ERROR: Required columns not found in Excel: {missing}")

    # ── connect to DB ────────────────────────────────────────────────────────
    print(f"\nConnecting to PostgreSQL: {DB_CONFIG['user']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    if dry_run:
        print("🔵  DRY-RUN mode: no changes will be committed.\n")

    data_rows = rows[1:]
    total = len(data_rows)
    print(f"Processing {total} student rows...\n")

    for row_num, row in enumerate(data_rows, start=2):  # 2 = Excel row 2
        # skip completely blank rows
        if all(cell.value is None for cell in row):
            continue

        try:
            data = parse_row(raw_headers, row)
        except Exception as exc:
            report.add_error(row_num, {}, exc)
            continue

        student_code = data.get("student_code") or None
        national_id  = data.get("national_id")  or None

        if not national_id and not student_code:
            report.add_error(row_num, data,
                             "Both national_id and student_code are empty — cannot identify student.")
            continue

        try:
            existing = find_existing_student(cur, student_code, national_id)

            if existing:
                # ── UPDATE path ──────────────────────────────────────────
                updatable_fields = [f for f in data.keys()
                                    if f not in ("id", "created_at", "updated_at")]
                current = get_current_values(cur, existing["id"], updatable_fields)

                # determine which fields actually changed
                changed_fields = []
                for field in updatable_fields:
                    new_val = data.get(field)
                    old_val = current.get(field)
                    # Normalise for comparison: None == ''
                    n = new_val if new_val is not None else ""
                    o = old_val if old_val is not None else ""
                    if str(n) != str(o):
                        changed_fields.append(field)

                if changed_fields:
                    if not dry_run:
                        update_student(cur, existing["id"], data, changed_fields)
                    report.add_updated(row_num, data, existing, changed_fields)
                else:
                    report.add_skipped(row_num, data, existing)

            else:
                # ── INSERT path ──────────────────────────────────────────
                if not dry_run:
                    new_id = insert_student(cur, data)
                else:
                    new_id = "(dry-run)"
                report.add_inserted(row_num, data, new_id)

        except Exception as exc:
            conn.rollback()
            report.add_error(row_num, data, exc)
            # re-open transaction
            cur = conn.cursor()
            continue

    if not dry_run:
        conn.commit()
        print("Changes committed to the database.")
    else:
        conn.rollback()

    cur.close()
    conn.close()
    wb.close()

    return report


# ═════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Upsert students from an Excel file into the production database."
    )
    parser.add_argument("excel_file", help="Path to the .xlsx file")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulate the import without making any DB changes"
    )
    parser.add_argument(
        "--report", metavar="FILE",
        help="Write the report to this file instead of (or in addition to) stdout"
    )
    args = parser.parse_args()

    excel_path = Path(args.excel_file).resolve()
    if not excel_path.exists():
        sys.exit(f"ERROR: File not found: {excel_path}")

    report = process_excel(excel_path, dry_run=args.dry_run)
    rendered = report.render()

    print(rendered)

    if args.report:
        report_path = Path(args.report)
        report_path.write_text(rendered, encoding="utf-8")
        print(f"\nReport saved to: {report_path}")

    # exit code 1 if any errors
    if report.errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
