#!/usr/bin/env bash
# =============================================================================
# fix_production_students.sh
#
# Fixes the UUID mismatch problem on production:
#   1. Diagnoses which students have mismatched UUIDs
#   2. Migrates student UUIDs to match the printed QR cards
#      - Cascades changes to student_attendance_records & student_teacher_links
#      - Merges attendance records if both old and new UUIDs have records
#        for the same date (keeps the earlier check-in, preserves check-out)
#   3. Inserts any students that don't exist yet
#   4. Inserts the historical attendance records from the SQL dump
#
# Usage:
#   chmod +x fix_production_students.sh
#   ./fix_production_students.sh              # dry-run (default)
#   ./fix_production_students.sh --apply      # actually apply changes
#
# Override connection details via env vars:
#   DB_HOST=myserver DB_NAME=mydb DB_USER=myuser PGPASSWORD=secret ./fix_production_students.sh
# =============================================================================
set -euo pipefail

# ── Mode ───────────────────────────────────────────────────────────────────
DRY_RUN=true
if [[ "${1:-}" == "--apply" ]]; then
    DRY_RUN=false
fi

# ── Connection settings ───────────────────────────────────────────────────
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-qr_attendance}"
DB_USER="${DB_USER:-postgres}"

PSQL_ARGS=(
    --host="$DB_HOST"
    --port="$DB_PORT"
    --dbname="$DB_NAME"
    --username="$DB_USER"
    --set ON_ERROR_STOP=1
)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATTENDANCE_SQL="${SCRIPT_DIR}/student_attendance_records_rows (1)(2).sql"

if [[ ! -f "$ATTENDANCE_SQL" ]]; then
    echo "ERROR: Attendance SQL file not found: $ATTENDANCE_SQL"
    exit 1
fi

echo "================================================"
echo " Production Student UUID Fix"
echo " Target: $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
if $DRY_RUN; then
    echo " Mode:   DRY RUN (use --apply to execute)"
else
    echo " Mode:   APPLYING CHANGES"
fi
echo "================================================"
echo ""

# ── Step 1: Diagnose ──────────────────────────────────────────────────────
echo "=== STEP 1: Diagnosing UUID mismatches ==="
echo ""

psql "${PSQL_ARGS[@]}" <<'DIAG_SQL'
SELECT
    s.id AS current_uuid,
    s.national_id,
    s.student_code,
    s.full_name,
    (SELECT COUNT(*) FROM student_attendance_records WHERE student_id = s.id) AS attendance_count,
    (SELECT COUNT(*) FROM student_teacher_links WHERE student_id = s.id) AS teacher_link_count
FROM students s
WHERE s.national_id IN (
    'MSC20260097','MSC20260044','MSC20260140','MSC20260136',
    'MSC20260123','MSC20260018','MSC20260082','MSC20260114'
)
ORDER BY s.national_id;
DIAG_SQL

echo ""
echo "Expected UUIDs (from QR cards / SQL dump):"
echo "  MSC20260097 → 012ba392-7a10-409a-b16b-ffe364d10cd0"
echo "  MSC20260044 → 01e81afa-189b-4d67-bf8b-1803a4418833"
echo "  MSC20260140 → 04b4169a-3b41-46df-b1b5-982aafdda037"
echo "  MSC20260136 → 07861704-bf1b-4856-ac32-53cd49726f2b"
echo "  MSC20260123 → 0d91c4ff-175a-4f65-87ca-21e3f61cd761"
echo "  MSC20260018 → 10ffae76-f8c3-43ea-91af-6795aa00f11d"
echo "  MSC20260082 → 116f5854-2102-492c-8de9-0e38d91e9865"
echo "  MSC20260114 → 122be224-fcad-45d9-b6ca-c63b4e7bc8de"
echo ""

if $DRY_RUN; then
    echo "=== DRY RUN — No changes will be made ==="
    echo "Review the output above. If UUIDs differ, run with --apply"
    echo ""
    exit 0
fi

# ── Step 2: Fix UUIDs + Insert missing students ──────────────────────────
echo "=== STEP 2: Fixing student UUIDs & inserting missing students ==="
echo ""

FIX_SQL="$(mktemp /tmp/fix_students_XXXXXX.sql)"
trap 'rm -f "$FIX_SQL"' EXIT

cat > "$FIX_SQL" << 'FIX_EOF'
BEGIN;

-- =====================================================================
-- PL/pgSQL block to fix student UUIDs
--
-- For each student:
--   1. If student exists with the WRONG UUID → migrate UUID + cascade FKs
--   2. If student doesn't exist → insert them
--   3. If student already has the correct UUID → skip
--
-- When migrating UUIDs, attendance records that were created via manual
-- student_code entry (which reference the old/wrong UUID) are re-pointed
-- to the desired UUID. If both UUIDs have records for the same date,
-- we keep the earlier check-in and merge check-out info.
-- =====================================================================
DO $$
DECLARE
    rec RECORD;
    old_id UUID;
    conflict_rec RECORD;
BEGIN
    FOR rec IN
        SELECT * FROM (VALUES
            ('012ba392-7a10-409a-b16b-ffe364d10cd0'::UUID, 'MSC20260097', 'صباحى097', 'محمد محسن توفيق عبدالعال', 'م.صباحى', '2026-06-12 11:56:05.614048+00'::TIMESTAMPTZ, '2026-06-22 13:09:01.167297+00'::TIMESTAMPTZ, '01002995587', '01010473896', 'M'::TEXT),
            ('01e81afa-189b-4d67-bf8b-1803a4418833'::UUID, 'MSC20260044', 'صباحى044', 'مروان محمد غريب محمد', 'م.صباحى', '2026-06-12 11:56:05.422259+00'::TIMESTAMPTZ, '2026-06-12 11:56:05.422268+00'::TIMESTAMPTZ, '01208029040', NULL, 'M'::TEXT),
            ('04b4169a-3b41-46df-b1b5-982aafdda037'::UUID, 'MSC20260140', 'صباحى140', 'محمد عبدالعاطى محمد على عبدالعاطى', 'م.صباحى', '2026-06-16 07:20:34.431704+00'::TIMESTAMPTZ, '2026-06-16 07:20:34.431712+00'::TIMESTAMPTZ, '01201456788', '01122366716', 'M'::TEXT),
            ('07861704-bf1b-4856-ac32-53cd49726f2b'::UUID, 'MSC20260136', 'صباحى136', 'آدم محمد شعبان السيد', 'م.صباحى', '2026-06-15 11:42:36.899696+00'::TIMESTAMPTZ, '2026-06-15 11:42:36.899705+00'::TIMESTAMPTZ, '01285404890', '01028101950', 'M'::TEXT),
            ('0d91c4ff-175a-4f65-87ca-21e3f61cd761'::UUID, 'MSC20260123', 'صباحى123', 'البراء سامح إبراهيم رمضان', 'م.صباحى', '2026-06-14 09:50:21.918505+00'::TIMESTAMPTZ, '2026-06-14 09:50:21.918514+00'::TIMESTAMPTZ, '01099399016', NULL, 'M'::TEXT),
            ('10ffae76-f8c3-43ea-91af-6795aa00f11d'::UUID, 'MSC20260018', 'صباحى018', 'حمزة هانى عبدالسلام عبدالرحيم', 'م.صباحى', '2026-06-12 11:56:05.327124+00'::TIMESTAMPTZ, '2026-06-12 11:56:05.327132+00'::TIMESTAMPTZ, '01223296403', '01061501655', 'M'::TEXT),
            ('116f5854-2102-492c-8de9-0e38d91e9865'::UUID, 'MSC20260082', 'صباحى082', 'محمد أحمد حسن عطية عبدالعزيز', 'م.صباحى', '2026-06-12 11:56:05.554132+00'::TIMESTAMPTZ, '2026-06-12 11:56:05.554141+00'::TIMESTAMPTZ, '01065071308', '01002986108', NULL),
            ('122be224-fcad-45d9-b6ca-c63b4e7bc8de'::UUID, 'MSC20260114', 'صباحى114', 'آنس بهاء محمد أمين', 'م.صباحى', '2026-06-12 11:56:05.668392+00'::TIMESTAMPTZ, '2026-06-12 11:56:05.668401+00'::TIMESTAMPTZ, '01090689400', NULL, NULL)
        ) AS t(desired_id, nat_id, stu_code, full_name, grade, created_at, updated_at, parent_phone, phone, gender)
    LOOP
        -- Look up the student by national_id or student_code
        SELECT id INTO old_id
        FROM students
        WHERE national_id = rec.nat_id OR student_code = rec.stu_code
        LIMIT 1;

        IF old_id IS NULL THEN
            -- Student doesn't exist at all → insert
            RAISE NOTICE '[INSERT] Student % (%) — inserting with UUID %',
                rec.full_name, rec.nat_id, rec.desired_id;

            INSERT INTO students (
                id, national_id, full_name, grade, created_at, updated_at,
                student_code, parent_phone, phone, gender, date_of_birth,
                hall_name, joining_date, nickname, notes, child_pickup_person,
                parent_address, parent_calls_phone, parent_full_name, parent_job,
                parent_marital_status, parent_qualification, parent_spouse_job
            ) VALUES (
                rec.desired_id, rec.nat_id, rec.full_name, rec.grade,
                rec.created_at, rec.updated_at, rec.stu_code, rec.parent_phone,
                rec.phone, rec.gender, NULL, '', NULL, '', '', '', '', NULL,
                '', '', '', '', ''
            );

        ELSIF old_id = rec.desired_id THEN
            -- Already has the correct UUID → nothing to do
            RAISE NOTICE '[OK] Student % (%) already has correct UUID %',
                rec.full_name, rec.nat_id, rec.desired_id;

        ELSE
            -- UUID mismatch! Need to migrate old_id → desired_id
            RAISE NOTICE '[MIGRATE] Student % (%) — changing UUID from % to %',
                rec.full_name, rec.nat_id, old_id, rec.desired_id;

            -- ── Handle attendance records ──
            -- There might be a conflict: the desired_id might already exist
            -- in student_attendance_records if a previous import partially
            -- succeeded. And old_id might have new records from manual entry.
            -- We need to merge carefully, respecting unique(student_id, date).

            FOR conflict_rec IN
                SELECT old_att.id AS old_att_id,
                       old_att.date AS att_date,
                       old_att.check_in_time AS old_checkin,
                       old_att.check_out_time AS old_checkout,
                       new_att.id AS new_att_id,
                       new_att.check_in_time AS new_checkin,
                       new_att.check_out_time AS new_checkout
                FROM student_attendance_records old_att
                INNER JOIN student_attendance_records new_att
                    ON old_att.date = new_att.date
                WHERE old_att.student_id = old_id
                  AND new_att.student_id = rec.desired_id
            LOOP
                -- Both the old UUID and the desired UUID have a record for
                -- the same date. Keep the one with the earlier check-in,
                -- and preserve checkout info from either.
                RAISE NOTICE '  [MERGE] Date %: merging attendance records', conflict_rec.att_date;

                -- Update the surviving record (under desired_id) with
                -- checkout time if only the old record has it
                IF conflict_rec.new_checkout IS NULL AND conflict_rec.old_checkout IS NOT NULL THEN
                    UPDATE student_attendance_records
                    SET check_out_time = conflict_rec.old_checkout
                    WHERE id = conflict_rec.new_att_id;
                END IF;

                -- If the old record has an earlier check-in, use it
                IF conflict_rec.old_checkin < conflict_rec.new_checkin THEN
                    UPDATE student_attendance_records
                    SET check_in_time = conflict_rec.old_checkin
                    WHERE id = conflict_rec.new_att_id;
                END IF;

                -- Delete the old conflicting record
                DELETE FROM student_attendance_records WHERE id = conflict_rec.old_att_id;
            END LOOP;

            -- Now move remaining (non-conflicting) attendance records
            UPDATE student_attendance_records
            SET student_id = rec.desired_id
            WHERE student_id = old_id;

            -- ── Handle teacher links ──
            -- Delete links that would conflict (same student+teacher pair)
            DELETE FROM student_teacher_links stl_old
            WHERE stl_old.student_id = old_id
              AND EXISTS (
                  SELECT 1 FROM student_teacher_links stl_new
                  WHERE stl_new.student_id = rec.desired_id
                    AND stl_new.teacher_id = stl_old.teacher_id
              );

            -- Move remaining teacher links
            UPDATE student_teacher_links
            SET student_id = rec.desired_id
            WHERE student_id = old_id;

            -- ── Finally update the student's primary key ──
            UPDATE students SET id = rec.desired_id WHERE id = old_id;
        END IF;
    END LOOP;
END $$;

COMMIT;
FIX_EOF

echo "Running UUID fix..."
psql "${PSQL_ARGS[@]}" --file="$FIX_SQL"
echo ""
echo "✓ Student UUIDs fixed"
echo ""

# ── Step 3: Insert historical attendance records ─────────────────────────
echo "=== STEP 3: Inserting historical attendance records ==="
echo ""

ATTENDANCE_IMPORT_SQL="$(mktemp /tmp/attendance_import_XXXXXX.sql)"
# Add to trap cleanup
trap 'rm -f "$FIX_SQL" "$ATTENDANCE_IMPORT_SQL"' EXIT

{
    echo "BEGIN;"
    echo ""
    echo "-- Insert attendance records, skip any that already exist"
    # The SQL file contains a single INSERT...VALUES statement ending with ;
    # We strip the trailing semicolon and add ON CONFLICT DO NOTHING
    sed 's/;[[:space:]]*$//' "$ATTENDANCE_SQL"
    echo ""
    echo "ON CONFLICT (id) DO NOTHING;"
    echo ""
    echo "COMMIT;"
} > "$ATTENDANCE_IMPORT_SQL"

psql "${PSQL_ARGS[@]}" --file="$ATTENDANCE_IMPORT_SQL"
echo ""
echo "✓ Historical attendance records imported"
echo ""

# ── Step 4: Verify ───────────────────────────────────────────────────────
echo "=== STEP 4: Verification ==="
echo ""

psql "${PSQL_ARGS[@]}" <<'VERIFY_SQL'
-- Show final state of all 8 students
SELECT
    s.id AS uuid,
    s.national_id,
    s.student_code,
    s.full_name,
    (SELECT COUNT(*) FROM student_attendance_records WHERE student_id = s.id) AS total_attendance_records,
    (SELECT COUNT(*) FROM student_teacher_links WHERE student_id = s.id) AS teacher_links
FROM students s
WHERE s.national_id IN (
    'MSC20260097','MSC20260044','MSC20260140','MSC20260136',
    'MSC20260123','MSC20260018','MSC20260082','MSC20260114'
)
ORDER BY s.national_id;
VERIFY_SQL

echo ""
echo "================================================"
echo " Done! QR codes should now work for all students."
echo "================================================"
