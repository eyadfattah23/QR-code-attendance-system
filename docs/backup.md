# النسخ الاحتياطي والاستعادة | Backup & Restore

---

## ما الذي يحتاج نسخاً احتياطياً؟

| المكوّن | الموقع | الأهمية |
|---|---|---|
| قاعدة البيانات | PostgreSQL | 🔴 حرجة — كل بيانات الطلاب والحضور |
| صور الحضور | `media/` | 🟡 مهمة — صور يومية للطلاب |
| ملف الإعدادات | `.env` | 🟡 مهمة — كلمات المرور والمفاتيح |
| الكود | `/opt/qr_attendance/` | 🟢 اختيارية — موجود على git |

---

## نسخ احتياطي لقاعدة البيانات | Database Backup

### نسخة احتياطية يدوية

```bash
sudo -u postgres pg_dump qr_attendance > backup_$(date +%Y%m%d_%H%M%S).sql
```

### نسخة احتياطية مضغوطة (موصى به)

```bash
sudo -u postgres pg_dump -Fc qr_attendance > backup_$(date +%Y%m%d_%H%M%S).dump
```

---

## نسخ احتياطي للصور | Media Backup

```bash
tar -czf media_backup_$(date +%Y%m%d).tar.gz /opt/qr_attendance/media/
```

---

## نسخ احتياطي تلقائي يومي | Automated Daily Backup

أنشئ سكريبت النسخ الاحتياطي:

```bash
sudo nano /opt/qr_attendance/backup.sh
```

```bash
#!/bin/bash
# Daily backup script for QR Attendance System

BACKUP_DIR="/backups/qr_attendance"
DATE=$(date +%Y%m%d_%H%M%S)
KEEP_DAYS=30

mkdir -p "$BACKUP_DIR"

# Backup database
sudo -u postgres pg_dump -Fc qr_attendance > "$BACKUP_DIR/db_$DATE.dump"

# Backup media files
tar -czf "$BACKUP_DIR/media_$DATE.tar.gz" /opt/qr_attendance/media/

# Backup .env
cp /opt/qr_attendance/.env "$BACKUP_DIR/env_$DATE.bak"

# Delete backups older than KEEP_DAYS days
find "$BACKUP_DIR" -type f -mtime +$KEEP_DAYS -delete

echo "Backup completed: $DATE"
```

```bash
sudo chmod +x /opt/qr_attendance/backup.sh
sudo mkdir -p /backups/qr_attendance
```

أضفه إلى cron ليعمل كل يوم في الساعة 2 صباحاً:

```bash
sudo crontab -e
```

أضف السطر:
```
0 2 * * * /opt/qr_attendance/backup.sh >> /var/log/qr_backup.log 2>&1
```

---

## استعادة قاعدة البيانات | Restore Database

### من ملف `.sql`

```bash
sudo -u postgres psql qr_attendance < backup_20260101_020000.sql
```

### من ملف `.dump` (مضغوط)

```bash
sudo -u postgres pg_restore -d qr_attendance backup_20260101_020000.dump
```

> ⚠️ إذا كانت قاعدة البيانات موجودة وبها بيانات، احذفها أولاً:
> ```bash
> sudo -u postgres dropdb qr_attendance
> sudo -u postgres createdb qr_attendance
> sudo -u postgres psql -c "GRANT ALL ON DATABASE qr_attendance TO qr_attendance;"
> ```

### بعد الاستعادة

```bash
cd /opt/qr_attendance
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=qr_attendance.settings.production
python manage.py migrate  # للتأكد من تطبيق أي مايجريشن جديدة
```

---

## استعادة الصور | Restore Media

```bash
tar -xzf media_backup_20260101.tar.gz -C /
```

---

## عمليات النقل إلى جهاز جديد | Moving to a New Server

1. على الجهاز القديم:
```bash
sudo -u postgres pg_dump -Fc qr_attendance > full_backup.dump
tar -czf media.tar.gz /opt/qr_attendance/media/
cp /opt/qr_attendance/.env env.bak
```

2. انقل الملفات الثلاثة إلى الجهاز الجديد (USB أو شبكة محلية):
```bash
scp full_backup.dump media.tar.gz env.bak user@new-server:/tmp/
```

3. على الجهاز الجديد، اتبع `docs/deployment.md` ثم استعد البيانات.

---

## التحقق من النسخة الاحتياطية | Verify Backup

```bash
# عرض محتويات ملف dump
pg_restore --list backup_20260101.dump | head -20

# حجم الملفات
ls -lh /backups/qr_attendance/
```
