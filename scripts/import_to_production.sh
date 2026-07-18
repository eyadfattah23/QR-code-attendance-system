#!/usr/bin/env bash
# =============================================================================
# import_to_production.sh
#
# Usage:
#   chmod +x import_to_production.sh
#   ./import_to_production.sh
#
# Override connection details via env vars:
#   DB_HOST=myserver DB_NAME=mydb DB_USER=myuser PGPASSWORD=secret ./import_to_production.sh
# =============================================================================
set -euo pipefail

# ── Connection settings ────────────────────────────────────────────────────
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-qr_attendance}"
DB_USER="${DB_USER:-postgres}"
# Set PGPASSWORD in the environment to avoid interactive prompts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATTENDANCE_SQL="${SCRIPT_DIR}/student_attendance_records_rows (1)(2).sql"

if [[ ! -f "$ATTENDANCE_SQL" ]]; then
  echo "ERROR: Attendance SQL file not found: $ATTENDANCE_SQL"
  exit 1
fi

# ── Write students SQL to a temp file ─────────────────────────────────────
STUDENTS_SQL="$(mktemp /tmp/students_XXXXXX.sql)"
COMBINED_SQL="$(mktemp /tmp/import_combined_XXXXXX.sql)"
trap 'rm -f "$STUDENTS_SQL" "$COMBINED_SQL"' EXIT

cat > "$STUDENTS_SQL" << 'STUDENTS_EOF'
INSERT INTO "public"."students" (
  "id","national_id","full_name","grade","created_at","updated_at",
  "student_code","parent_phone","phone","gender","date_of_birth",
  "hall_name","joining_date","nickname","notes","child_pickup_person",
  "parent_address","parent_calls_phone","parent_full_name","parent_job",
  "parent_marital_status","parent_qualification","parent_spouse_job"
) VALUES
  ('012ba392-7a10-409a-b16b-ffe364d10cd0','MSC20260097','محمد محسن توفيق عبدالعال','م.صباحى','2026-06-12 11:56:05.614048+00','2026-06-22 13:09:01.167297+00','صباحى097','01002995587','01010473896','M',null,'',null,'','','','',null,'','','','',''),
  ('01e81afa-189b-4d67-bf8b-1803a4418833','MSC20260044','مروان محمد غريب محمد','م.صباحى','2026-06-12 11:56:05.422259+00','2026-06-12 11:56:05.422268+00','صباحى044','01208029040',null,'M',null,'',null,'','','','',null,'','','','',''),
  ('04b4169a-3b41-46df-b1b5-982aafdda037','MSC20260140','محمد عبدالعاطى محمد على عبدالعاطى','م.صباحى','2026-06-16 07:20:34.431704+00','2026-06-16 07:20:34.431712+00','صباحى140','01201456788','01122366716','M',null,'',null,'','','','',null,'','','','',''),
  ('07861704-bf1b-4856-ac32-53cd49726f2b','MSC20260136','آدم محمد شعبان السيد','م.صباحى','2026-06-15 11:42:36.899696+00','2026-06-15 11:42:36.899705+00','صباحى136','01285404890','01028101950','M',null,'',null,'','','','',null,'','','','',''),
  ('0d91c4ff-175a-4f65-87ca-21e3f61cd761','MSC20260123','البراء سامح إبراهيم رمضان','م.صباحى','2026-06-14 09:50:21.918505+00','2026-06-14 09:50:21.918514+00','صباحى123','01099399016',null,'M',null,'',null,'','','','',null,'','','','',''),
  ('10ffae76-f8c3-43ea-91af-6795aa00f11d','MSC20260018','حمزة هانى عبدالسلام عبدالرحيم','م.صباحى','2026-06-12 11:56:05.327124+00','2026-06-12 11:56:05.327132+00','صباحى018','01223296403','01061501655','M',null,'',null,'','','','',null,'','','','',''),
  ('116f5854-2102-492c-8de9-0e38d91e9865','MSC20260082','محمد أحمد حسن عطية عبدالعزيز','م.صباحى','2026-06-12 11:56:05.554132+00','2026-06-12 11:56:05.554141+00','صباحى082','01065071308','01002986108',null,null,'',null,'','','','',null,'','','','',''),
  ('122be224-fcad-45d9-b6ca-c63b4e7bc8de','MSC20260114','آنس بهاء محمد أمين','م.صباحى','2026-06-12 11:56:05.668392+00','2026-06-12 11:56:05.668401+00','صباحى114','01090689400',null,null,null,'',null,'','','','',null,'','','','','')
ON CONFLICT (id) DO NOTHING;
STUDENTS_EOF

# ── Build one combined transaction ─────────────────────────────────────────
{
  echo "BEGIN;"
  echo ""
  echo "-- === STUDENTS ==="
  cat "$STUDENTS_SQL"
  echo ""
  echo "-- === ATTENDANCE RECORDS ==="
  # Strip trailing semicolon and add ON CONFLICT so re-runs are idempotent
  sed 's/;[[:space:]]*$//' "$ATTENDANCE_SQL"
  echo "ON CONFLICT (id) DO NOTHING;"
  echo ""
  echo "COMMIT;"
} > "$COMBINED_SQL"

# ── Run ────────────────────────────────────────────────────────────────────
echo "================================================"
echo " Importing to: $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
echo "================================================"

psql \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --dbname="$DB_NAME" \
  --username="$DB_USER" \
  --set ON_ERROR_STOP=1 \
  --file="$COMBINED_SQL"

echo ""
echo "================================================"
echo " Done."
echo "================================================"
