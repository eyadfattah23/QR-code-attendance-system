#!/usr/bin/env bash
# Daily PostgreSQL backup for qr_attendance
# Reads DB credentials from the project .env file
# Backups are kept for 30 days; older ones are deleted automatically.

set -euo pipefail

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"
BACKUP_DIR="/media/redwan_it/D6347BB9347B9AE7/db-backups"
LOG_FILE="$PROJECT_DIR/logs/backup.log"
RETENTION_DAYS=30

# ── Load .env ────────────────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: .env file not found at $ENV_FILE" >> "$LOG_FILE"
    exit 1
fi

# Export only DB_* variables from .env (skip comments and blanks)
while IFS='=' read -r key value; do
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    [[ "$key" =~ ^DB_ ]] && export "$key=$value"
done < "$ENV_FILE"

DB_NAME="${DB_NAME:-qr_attendance}"
DB_USER="${DB_USER:-qr_attendance}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# ── Verify backup drive is mounted ───────────────────────────────────────────
if [[ ! -d "$BACKUP_DIR" ]]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: Backup directory not found: $BACKUP_DIR (drive may not be mounted)" >> "$LOG_FILE"
    exit 1
fi

# ── Run pg_dump ───────────────────────────────────────────────────────────────
TIMESTAMP="$(date '+%Y-%m-%d_%H-%M-%S')"
BACKUP_FILE="$BACKUP_DIR/qr_attendance_${TIMESTAMP}.sql.gz"

PGPASSWORD="$DB_PASSWORD" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-password \
    | gzip > "$BACKUP_FILE"

echo "$(date '+%Y-%m-%d %H:%M:%S') OK: Backup saved to $BACKUP_FILE" >> "$LOG_FILE"

# ── Remove backups older than RETENTION_DAYS ─────────────────────────────────
find "$BACKUP_DIR" -maxdepth 1 -name "qr_attendance_*.sql.gz" \
    -mtime +"$RETENTION_DAYS" -delete

echo "$(date '+%Y-%m-%d %H:%M:%S') OK: Old backups (>${RETENTION_DAYS}d) cleaned up" >> "$LOG_FILE"
