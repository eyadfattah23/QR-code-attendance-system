# نظام المصادقة - Authentication System

## نظرة عامة | Overview

يوفر هذا النظام مصادقة آمنة للمستخدمين مع دعم كامل للغة العربية واتجاه RTL.

This module provides secure user authentication with full Arabic language support and RTL direction.

---

## الميزات | Features

- ✅ **تسجيل دخول آمن** - Secure login with CSRF protection
- ✅ **تصميم متجاوب** - Fully responsive design for all screen sizes
- ✅ **دعم الأدوار** - Role-based access control (Admin/Teacher)
- ✅ **رسائل عربية** - Arabic error messages and notifications
- ✅ **حماية من الهجمات** - Protection against common attacks

---

## هيكل الملفات | File Structure

```
core/
├── forms.py          # LoginForm - نموذج تسجيل الدخول
├── views.py          # Authentication views - عرض المصادقة
├── urls.py           # URL routing - مسارات الروابط
├── models.py         # User model - نموذج المستخدم
└── tests/
    ├── test_forms.py   # Form tests
    ├── test_views.py   # View tests
    └── test_models.py  # Model tests

templates/
├── base.html                  # Base template - القالب الأساسي
└── auth/
    └── login.html             # Login page - صفحة تسجيل الدخول

admin_portal/
├── views.py          # Admin dashboard view
└── urls.py           # Admin URL routing

teacher_portal/
├── views.py          # Teacher dashboard view
└── urls.py           # Teacher URL routing
```

---

## المسارات | URL Routes

| المسار | الاسم | الوصف |
|--------|-------|-------|
| `/` | `login` | صفحة تسجيل الدخول |
| `/login/` | `login` | صفحة تسجيل الدخول |
| `/logout/` | `logout` | تسجيل الخروج |
| `/dashboard/` | `dashboard` | إعادة توجيه للوحة التحكم |
| `/portal/admin/` | `admin_portal:dashboard` | لوحة تحكم المدير |
| `/portal/teacher/` | `teacher_portal:dashboard` | لوحة تحكم المعلم |

---

## نموذج المستخدم | User Model

### الأدوار | Roles

```python
class Role(models.TextChoices):
    ADMIN = 'admin', 'Admin'      # المدير - Full system access
    TEACHER = 'teacher', 'Teacher' # المعلم - Limited access
```

### الخصائص | Properties

| الخاصية | النوع | الوصف |
|---------|-------|-------|
| `is_admin` | bool | هل المستخدم مدير؟ |
| `is_teacher` | bool | هل المستخدم معلم؟ |
| `phone` | str | رقم الهاتف (مطلوب، 11 رقم يبدأ بصفر) |
| `USERNAME_FIELD` | str | 'phone' - المصادقة عبر رقم الهاتف |

### مثال الاستخدام | Usage Example

```python
from core.models import User

# Create admin user (phone is required - 11 digits starting with 0)
admin = User.objects.create_user(
    phone='01234567890',
    password='secure_password',
    role=User.Role.ADMIN,
    first_name='أحمد',
    last_name='محمد'
)

# Check role
if user.is_admin:
    # Admin logic
    pass
elif user.is_teacher:
    # Teacher logic
    pass
```

---

## نموذج تسجيل الدخول | LoginForm

### الوصف | Description

نموذج Django للتحقق من بيانات اعتماد المستخدم.

### الحقول | Fields

| الحقل | النوع | المطلوب | الوصف |
|-------|-------|---------|-------|
| `phone` | CharField | ✅ | رقم الهاتف (11 رقم يبدأ بصفر) |
| `password` | CharField | ✅ | كلمة المرور |

### تنسيق رقم الهاتف | Phone Format

- **الطول:** 11 رقم بالضبط
- **البداية:** يجب أن يبدأ بصفر (0)
- **مثال:** `01234567890`
- **النمط:** `^0\d{10}$`

### رسائل الخطأ | Error Messages

| الحالة | الرسالة |
|--------|---------|
| Phone empty | رقم الهاتف مطلوب |
| Invalid phone format | رقم الهاتف يجب أن يكون 11 رقم ويبدأ بصفر (مثال: 01234567890) |
| Password empty | كلمة المرور مطلوبة |
| Invalid credentials | رقم الهاتف أو كلمة المرور غير صحيحة |
| Inactive account | هذا الحساب معطل. يرجى التواصل مع المسؤول |

### مثال الاستخدام | Usage Example

```python
from core.forms import LoginForm

# In view
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request=request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = LoginForm()
    
    return render(request, 'auth/login.html', {'form': form})
```

---

## العروض | Views

### `login_view`

**المسار:** `/login/`  
**الطرق:** GET, POST  
**القوالب:** `auth/login.html`

يعالج تسجيل دخول المستخدم. يعيد توجيه المستخدمين المصادق عليهم إلى لوحة التحكم.

**المُزخرفات | Decorators:**
- `@never_cache` - يمنع تخزين الصفحة
- `@csrf_protect` - حماية CSRF
- `@require_http_methods(["GET", "POST"])` - يقبل GET و POST فقط

### `logout_view`

**المسار:** `/logout/`  
**الطرق:** GET, POST

يسجل خروج المستخدم ويعرض رسالة نجاح.

### `dashboard_redirect`

**المسار:** `/dashboard/`  
**الطرق:** GET

يعيد توجيه المستخدم إلى لوحة التحكم المناسبة بناءً على دوره:
- **Admin** → `/portal/admin/`
- **Teacher** → `/portal/teacher/`

---

## التحكم في الوصول | Access Control

### مُزخرِف المدير | Admin Decorator

```python
from admin_portal.views import admin_required

@admin_required
def admin_only_view(request):
    # Only admins can access
    pass
```

### مُزخرِف المعلم | Teacher Decorator

```python
from teacher_portal.views import teacher_required

@teacher_required
def teacher_only_view(request):
    # Only teachers can access
    pass
```

---

## التصميم المتجاوب | Responsive Design

### نقاط التوقف | Breakpoints

| الحجم | العرض | التعديلات |
|-------|-------|-----------|
| Mobile | < 576px | تقليل الحشو، أيقونات أصغر |
| Tablet | 576px - 767px | عرض بطاقة 380px |
| Desktop | ≥ 768px | عرض بطاقة 420px كحد أقصى |
| Landscape | height < 500px | تخطيط مضغوط |

### ميزات واجهة المستخدم | UI Features

- **تبديل كلمة المرور** - إظهار/إخفاء كلمة المرور
- **حالة التحميل** - مؤشر تحميل عند الإرسال
- **التحقق من جانب العميل** - التحقق الأساسي قبل الإرسال
- **الحركات** - حركة fadeInUp ناعمة

---

## الاختبارات | Testing

### تشغيل الاختبارات | Running Tests

```bash
# Run all auth tests
python manage.py test core.tests

# Run specific test file
python manage.py test core.tests.test_forms
python manage.py test core.tests.test_views
python manage.py test core.tests.test_models

# Run with pytest (recommended)
pytest core/tests/ -v

# Run with coverage
pytest core/tests/ --cov=core --cov-report=html
```

### تغطية الاختبارات | Test Coverage

| الملف | التغطية |
|-------|---------|
| forms.py | نموذج تسجيل الدخول، التحقق، المصادقة |
| views.py | تسجيل الدخول/الخروج، إعادة التوجيه |
| models.py | User model، الأدوار، الخصائص |

---

## الأمان | Security

### الحماية المُطبقة | Implemented Protections

1. **CSRF Protection** - حماية من هجمات CSRF
2. **Password Hashing** - تشفير كلمات المرور
3. **Session Security** - أمان الجلسات
4. **Safe Redirects** - إعادة توجيه آمنة (no open redirects)
5. **Cache Control** - منع تخزين صفحات المصادقة

### التوصيات | Recommendations

```python
# settings.py recommendations
SESSION_COOKIE_SECURE = True  # In production
CSRF_COOKIE_SECURE = True     # In production
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
```

---

## استكشاف الأخطاء | Troubleshooting

### مشاكل شائعة | Common Issues

#### 1. "رقم الهاتف أو كلمة المرور غير صحيحة"
- تأكد من صحة رقم الهاتف وكلمة المرور
- تحقق من أن رقم الهاتف 11 رقم ويبدأ بصفر
- تحقق من أن الحساب نشط (is_active=True)

#### 2. "رقم الهاتف يجب أن يكون 11 رقم ويبدأ بصفر"
- أدخل رقم الهاتف بالتنسيق الصحيح
- مثال: 01234567890

#### 3. "هذا الحساب معطل"
- تواصل مع المدير لتفعيل الحساب
- `User.objects.filter(phone='01234567890').update(is_active=True)`

#### 4. إعادة التوجيه لا تعمل
- تحقق من إعدادات LOGIN_URL في settings.py
- تأكد من تعريف المسارات بشكل صحيح

---

## المراجع | References

- [Django Authentication](https://docs.djangoproject.com/en/5.0/topics/auth/)
- [Bootstrap 5 RTL](https://getbootstrap.com/docs/5.3/getting-started/rtl/)
- [Django Testing](https://docs.djangoproject.com/en/5.0/topics/testing/)
