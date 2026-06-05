# إعدادات النظام | Configuration Reference

---

## ملف `.env`

يُقرأ تلقائياً عبر مكتبة `python-decouple`. انسخ `.env.example` وعدّله:

```bash
cp .env.example .env
```

### جميع المتغيرات المتاحة

| المتغير | مطلوب | القيمة الافتراضية | الوصف |
|---|---|---|---|
| `SECRET_KEY` | ✅ في production | مفتاح تجريبي غير آمن | مفتاح تشفير Django — يجب أن يكون طويلاً وعشوائياً |
| `DB_NAME` | ✅ في production | `qr_attendance` | اسم قاعدة البيانات PostgreSQL |
| `DB_USER` | ✅ في production | `qr_attendance` | مستخدم قاعدة البيانات |
| `DB_PASSWORD` | ✅ في production | — | كلمة مرور قاعدة البيانات |
| `DB_HOST` | ❌ | `localhost` | عنوان خادم قاعدة البيانات |
| `DB_PORT` | ❌ | `5432` | منفذ PostgreSQL |
| `ALLOWED_HOSTS` | ✅ في production | `localhost,127.0.0.1` | قائمة العناوين المسموح بها (مفصولة بفواصل) |
| `TIME_ZONE` | ❌ | `Africa/Cairo` | المنطقة الزمنية |

### مثال على ملف `.env` للإنتاج

```env
SECRET_KEY=your-very-long-random-secret-key-here
DB_NAME=qr_attendance
DB_USER=qr_attendance
DB_PASSWORD=StrongPassword123!
DB_HOST=localhost
DB_PORT=5432
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.5
TIME_ZONE=Africa/Cairo
```

---

## متغير `DJANGO_SETTINGS_MODULE`

| البيئة | القيمة |
|---|---|
| تطوير (development) | `qr_attendance.settings.development` |
| إنتاج (production) | `qr_attendance.settings.production` |

**للضبط في الجلسة الحالية:**
```bash
export DJANGO_SETTINGS_MODULE=qr_attendance.settings.production
```

**أو في ملف الخدمة systemd** (انظر `docs/deployment.md`).

---

## الفرق بين بيئة التطوير والإنتاج

| الإعداد | development | production |
|---|---|---|
| `DEBUG` | `True` | `False` |
| قاعدة البيانات | SQLite (`db.sqlite3`) | PostgreSQL |
| `ALLOWED_HOSTS` | `['*']` | قائمة محددة من `.env` |
| الأخطاء | تُعرض في المتصفح | تُكتب في السجلات فقط |
| `collectstatic` | غير مطلوب | مطلوب قبل التشغيل |

---

## الملفات الثابتة والوسائط

```python
STATIC_URL  = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']   # مصدر الملفات في التطوير
STATIC_ROOT = BASE_DIR / 'staticfiles'     # وجهة collectstatic في الإنتاج

MEDIA_URL  = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'            # صور الحضور المرفوعة
```

في الإنتاج، بعد أي تحديث للكود:
```bash
python manage.py collectstatic --noinput
```

---

## البنية الكاملة للمجلدات

```
qr_attendance/
├── .env                        ← إعداداتك (لا تُرفع على git)
├── .env.example                ← نموذج للإعدادات
├── manage.py
├── requirements.txt
│
├── qr_attendance/
│   └── settings/
│       ├── base.py             ← إعدادات مشتركة
│       ├── development.py      ← SQLite، DEBUG=True
│       └── production.py       ← PostgreSQL، DEBUG=False
│
├── static/                     ← ملفات Bootstrap وJS المحلية
│   ├── css/
│   │   ├── bootstrap.rtl.min.css
│   │   ├── bootstrap-icons.min.css
│   │   └── fonts/
│   └── js/
│       ├── bootstrap.bundle.min.js
│       └── htmx.min.js
│
├── media/                      ← صور الحضور (تنمو مع الوقت)
├── staticfiles/                ← مخرجات collectstatic (لا تُعدّل يدوياً)
└── logs/                       ← سجلات gunicorn
```

---

## المنطقة الزمنية

القيمة الافتراضية `Africa/Cairo` (توقيت مصر EET/EEST).

قائمة المناطق الزمنية المتاحة:
```bash
python3 -c "import zoneinfo; print('\n'.join(sorted(zoneinfo.available_timezones())))" | grep Africa
```
