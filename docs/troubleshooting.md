# استكشاف الأخطاء وإصلاحها | Troubleshooting

---

## مشاكل التشغيل | Startup Issues

### ❌ `That port is already in use`

المنفذ 8000 يستخدمه تطبيق آخر.

```bash
# اعرف من يستخدم المنفذ
sudo ss -tlnp | grep 8000

# أوقفه
sudo kill -9 <PID>

# أو استخدم منفذاً مختلفاً
python manage.py runserver 0.0.0.0:8080
```

---

### ❌ `DisallowedHost` — صفحة خطأ 400

```
Invalid HTTP_HOST header: '192.168.1.5'. You may need to add '192.168.1.5' to ALLOWED_HOSTS.
```

**الحل:** أضف العنوان إلى `.env`:
```
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.5
```
ثم أعد تشغيل الخادم.

---

### ❌ الصفحات تُحمَّل بدون CSS (تظهر كنص فقط)

**أسباب محتملة:**

1. **الملفات الثابتة لم تُجمع** (في بيئة الإنتاج):
```bash
python manage.py collectstatic --noinput
```

2. **`DEBUG=False` بدون تقديم الملفات الثابتة:**
   في الإنتاج، Django لا يقدم `static/` تلقائياً. إما فعّل DEBUG مؤقتاً أو أضف للـ urls.py:
```python
# qr_attendance/urls.py — للتطوير المحلي فقط
from django.conf import settings
from django.conf.urls.static import static
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

3. **ملفات Bootstrap غير موجودة في `static/`:**
```bash
ls static/css/bootstrap.rtl.min.css
ls static/js/bootstrap.bundle.min.js
```
إذا لم تكن موجودة، ارجع إلى [تعليمات تحميلها](configuration.md).

---

### ❌ `ModuleNotFoundError` عند التشغيل

```bash
source venv/bin/activate  # تأكد من تفعيل البيئة الافتراضية
pip install -r requirements.txt
```

---

### ❌ `django.db.utils.OperationalError: no such table`

المايجريشن لم تُطبَّق:
```bash
python manage.py migrate
```

---

### ❌ خطأ في الاتصال بـ PostgreSQL

```
django.db.utils.OperationalError: could not connect to server
```

```bash
# تحقق أن PostgreSQL يعمل
sudo systemctl status postgresql

# أعده تشغيله إذا توقف
sudo systemctl start postgresql

# تحقق من بيانات الاتصال في .env
cat .env | grep DB_
```

---

## مشاكل المسح | Scanning Issues

### ❌ رمز QR يُقرأ لكن لا يُسجَّل الحضور

- تأكد أن الطالب/المعلم موجود في قاعدة البيانات
- تأكد أن الـ UUID في بطاقة QR مطابق لـ `id` في قاعدة البيانات
- إذا كانت البطاقة قديمة وأُعيد إنشاء قاعدة البيانات، يجب إعادة طباعة البطاقات

### ❌ الماسح الضوئي لا يُرسل بعد المسح (Batch Mode)

- الضبط الافتراضي للـ Netum NT-1228BL يُرسل Enter بعد كل مسح
- إذا أردت وضع الدُفعة (Batch)، اضبط الماسح على إرسال newline فقط بدون Enter (راجع دليل الجهاز)

---

## مشاكل الصور | Photo Upload Issues

### ❌ الصور لا تُحفظ أو تُعرض

```bash
# تأكد أن مجلد media موجود وله صلاحيات الكتابة
ls -la /opt/qr_attendance/media/
sudo chown -R www-data:www-data /opt/qr_attendance/media/
sudo chmod -R 755 /opt/qr_attendance/media/
```

---

## مشاكل الخدمة (systemd) | Service Issues

### ❌ الخدمة لا تبدأ

```bash
# عرض السبب
sudo journalctl -u qr_attendance -n 50 --no-pager

# عرض حالة الخدمة
sudo systemctl status qr_attendance
```

**أخطاء شائعة:**
- `Permission denied` → مشكلة في صلاحيات المجلد:
```bash
sudo chown -R www-data:www-data /opt/qr_attendance
```
- `No such file` → تحقق من المسار في ملف الخدمة `/etc/systemd/system/qr_attendance.service`
- `ModuleNotFoundError` → gunicorn لا يُشغَّل من البيئة الافتراضية الصحيحة، تأكد أن المسار يشير إلى `venv/bin/gunicorn`

---

## مشاكل النسخ الاحتياطي | Backup Issues

### ❌ `pg_dump: error: connection to server failed`

```bash
# تشغيل pg_dump كمستخدم postgres
sudo -u postgres pg_dump qr_attendance > backup.sql
```

### ❌ مجلد النسخ الاحتياطي ممتلئ

```bash
# افحص المساحة
df -h /backups/

# احذف النسخ القديمة يدوياً
find /backups/qr_attendance/ -type f -mtime +60 -delete
```

---

## أوامر تشخيصية مفيدة | Useful Diagnostic Commands

```bash
# عرض سجلات الخادم مباشرة
sudo journalctl -u qr_attendance -f

# اختبار الإعدادات
python manage.py check --deploy

# عرض جميع المسارات المسجلة
python manage.py show_urls

# فتح shell Django للتحقق من البيانات
python manage.py shell
>>> from core.models import Student
>>> Student.objects.count()

# عرض الاتصالات الشبكية النشطة على المنفذ 8000
sudo ss -tlnp | grep 8000

# اختبار الوصول من الخادم نفسه
curl -I http://localhost:8000
```
