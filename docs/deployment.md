# دليل النشر على Ubuntu Server | Deployment Guide

نشر نظام الحضور على جهاز Ubuntu Server محلي متصل بالشبكة الداخلية.

---

## المتطلبات | Requirements

| المكون | الإصدار |
|---|---|
| Ubuntu Server | 22.04 LTS أو أحدث |
| Python | 3.11 أو أحدث |
| PostgreSQL | 14 أو أحدث |
| RAM | 2 GB كحد أدنى |
| Storage | 20 GB كحد أدنى (الصور تنمو بمرور الوقت) |

---

## 1. تحضير الجهاز | Prepare the Server

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git postgresql postgresql-contrib
```

---

## 2. إعداد قاعدة البيانات | Setup PostgreSQL

```bash
sudo -u postgres psql
```

داخل psql:
```sql
CREATE DATABASE qr_attendance;
CREATE USER qr_attendance WITH PASSWORD 'your-strong-password';
GRANT ALL PRIVILEGES ON DATABASE qr_attendance TO qr_attendance;
\q
```

---

## 3. نسخ الكود | Clone the Project

```bash
cd /opt
sudo git clone <your-repo-url> qr_attendance
sudo chown -R $USER:$USER /opt/qr_attendance
cd /opt/qr_attendance
```

---

## 4. البيئة الافتراضية والحزم | Virtual Environment & Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 5. ملف الإعدادات | Environment File

```bash
cp .env.example .env
nano .env
```

اضبط القيم:
```
SECRET_KEY=<generated-key>
DB_NAME=qr_attendance
DB_USER=qr_attendance
DB_PASSWORD=your-strong-password
DB_HOST=localhost
DB_PORT=5432
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.5
TIME_ZONE=Africa/Cairo
```

لتوليد `SECRET_KEY`:
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## 6. تشغيل المايجريشن وجمع الملفات الثابتة | Migrate & Collect Static

```bash
export DJANGO_SETTINGS_MODULE=qr_attendance.settings.production
python manage.py migrate
python manage.py collectstatic --noinput
```

---

## 7. إنشاء حساب المدير | Create Admin User

```bash
python manage.py seed_admin
```

أو يدوياً:
```bash
python manage.py shell
```
```python
from core.models import User
User.objects.create_superuser(phone='01000000000', password='your-password', role='admin')
exit()
```

---

## 8. إعداد Gunicorn | Setup Gunicorn

```bash
pip install gunicorn
```

اختبر أنه يعمل:
```bash
gunicorn --bind 0.0.0.0:8000 qr_attendance.wsgi:application
```

---

## 9. تشغيل تلقائي عبر systemd | systemd Service

أنشئ الملف `/etc/systemd/system/qr_attendance.service`:

```bash
sudo nano /etc/systemd/system/qr_attendance.service
```

```ini
[Unit]
Description=QR Attendance System
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/qr_attendance
Environment="DJANGO_SETTINGS_MODULE=qr_attendance.settings.production"
EnvironmentFile=/opt/qr_attendance/.env
ExecStart=/opt/qr_attendance/venv/bin/gunicorn \
    --workers 2 \
    --bind 0.0.0.0:8000 \
    --access-logfile /opt/qr_attendance/logs/access.log \
    --error-logfile /opt/qr_attendance/logs/error.log \
    qr_attendance.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo mkdir -p /opt/qr_attendance/logs
sudo chown -R www-data:www-data /opt/qr_attendance
sudo systemctl daemon-reload
sudo systemctl enable qr_attendance
sudo systemctl start qr_attendance
sudo systemctl status qr_attendance
```

---

## 10. إعداد الجدار الناري | Firewall

للوصول على المنفذ 8000 من الشبكة المحلية:

```bash
sudo ufw allow 8000
sudo ufw enable
```

أو لإعادة توجيه المنفذ 80 إلى 8000 (حتى لا تكتب :8000 في المتصفح):

```bash
sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8000
sudo apt install iptables-persistent
sudo netfilter-persistent save
```

---

## 11. التحقق | Verify

من جهاز آخر على نفس الشبكة:
```
http://192.168.1.5:8000
```

---

## أوامر مفيدة | Useful Commands

```bash
# إعادة تشغيل الخدمة
sudo systemctl restart qr_attendance

# عرض السجلات المباشرة
sudo journalctl -u qr_attendance -f

# عرض سجلات gunicorn
tail -f /opt/qr_attendance/logs/error.log

# تطبيق مايجريشن جديدة بعد تحديث الكود
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=qr_attendance.settings.production
python manage.py migrate
sudo systemctl restart qr_attendance
```
