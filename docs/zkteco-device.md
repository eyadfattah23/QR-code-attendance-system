# ربط جهاز البصمة ZKTeco K40 Pro | ZKTeco K40 Pro Fingerprint Device

تسجيل حضور وانصراف المعلمين بالبصمة، بنفس قواعد محطة المسح.

Teachers punch on the fingerprint device. The device pushes each punch to the server, and the server records check-in and check-out with the same rules as the scan station.

---

## نظرة عامة | Overview

```
 جهاز البصمة (ADMS)                      الخادم 192.168.1.6
┌──────────────────┐   HTTP :80   ┌────────────────────────────────────┐
│ K40 Pro          │ ───────────▶ │ /iclock/cdata   ← البصمات (ATTLOG)  │
│ User ID = 105    │ ◀─────────── │ /iclock/getrequest ← نبض كل 10 ث    │
└──────────────────┘     OK       │        ↓                           │
                                  │ رقم جهاز البصمة 105 → المعلم       │
                                  │        ↓                           │
                                  │ حضور / انصراف (نفس قواعد المحطة)  │
                                  └────────────────────────────────────┘
```

- **الجهاز هو من يتصل بالخادم** (وضع ADMS / Push). لا يحتاج الخادم أن يصل إلى الجهاز، ولا يُستخدم المنفذ 4370.
  The device opens every connection, so the server never needs to reach the device and port 4370 is not used.
- كل معلم له **"رقم جهاز البصمة"** في صفحة المعلم، ويجب أن يساوي **User ID** المسجل له على الجهاز.
  Each teacher has a "device number" in the admin portal, and it must equal their User ID on the device.
- **قواعد البصمات في اليوم الواحد** (نفس محطة المسح) | **Daily rules (same as the scan station):**

  | البصمة | النتيجة |
  |---|---|
  | الأولى | **حضور** بوقت البصمة |
  | خلال 5 دقائق من الحضور | تُتجاهل (بصمة مكررة) |
  | التالية (بعد 5 دقائق أو أكثر) | **انصراف** بوقت البصمة |
  | أي بصمة بعد الانصراف | تُتجاهل |
  | يوم مسجل فيه "غياب بإذن" | تُتجاهل |

- يُستخدم **وقت البصمة من الجهاز** وليس وقت وصولها. لذلك إذا انقطع الاتصال يحتفظ الجهاز بالبصمات ويرسلها لاحقاً، وتُسجَّل في يومها الصحيح.
  The punch time comes from the device. If the server is unreachable, the device keeps the punches and uploads them later with their original times.
- **كل بصمة تُحفظ في سجل** "Device punches" مع نتيجتها، حتى المرفوضة، للمراجعة.
  Every punch is saved in a log with its result, including rejected ones.
- شاشة الجهاز تعرض "تم التحقق" دائماً عند قبول البصمة. أما قرار الحضور أو الانصراف أو التجاهل فيتخذه الخادم، ويظهر في السجل.
  The device screen always says "Verified". The attendance decision is made by the server and shows in the log.
- هذا الإصدار **للمعلمين فقط**. الطلاب يستمرون بأكواد QR.

---

## الخطوات باختصار | Checklist

1. تحديث كود الخادم وتشغيل المايجريشن ← [القسم 1](#1-تحديث-الخادم--update-the-server)
2. التأكد أن `http://192.168.1.6/iclock/` يصل للنظام ← [القسم 2](#2-التأكد-من-المنفذ-80--check-port-80)
3. نقل الجهاز إلى شبكة الخادم 192.168.1.x ← [القسم 3](#3-شبكة-الجهاز--device-network)
4. ضبط Cloud Server Setting على الجهاز ← [القسم 4](#4-إعداد-الخادم-على-الجهاز--cloud-server-setting)
5. ضبط تاريخ ووقت الجهاز ← [القسم 5](#5-التاريخ-والوقت--date--time)
6. اعتماد الجهاز من لوحة Django ← [القسم 6](#6-اعتماد-الجهاز--approve-the-device)
7. إعطاء كل معلم رقماً وتسجيل بصمته بنفس الرقم ← [القسم 7](#7-تسجيل-المعلمين--enroll-teachers)
8. تجربة كاملة ← [القسم 8](#8-تجربة-كاملة--end-to-end-test)

> **الترتيب مهم:** اعتمد الجهاز (6) **قبل** إدخال أرقام المعلمين (7). عند اعتماد الجهاز يرسل كل البصمات القديمة المخزنة فيه، ولأن أرقام المعلمين لم تُدخل بعد، تُحفظ في السجل كـ"رقم غير مرتبط" ولا تُنشئ حضوراً قديماً.
> **Order matters:** approve the device before entering teacher numbers. On approval the device uploads its old stored punches. With no numbers assigned yet, they are only logged and create no attendance.

---

## 1. تحديث الخادم | Update the server

> ملف `deployment.md` قد لا يطابق الخادم الحالي. لذلك اقرأ القيم الفعلية من الخادم أولاً.
> `deployment.md` may be out of date, so read the real values from the server first.

```bash
# اسم الخدمة الفعلي
systemctl list-units --type=service | grep -i -E 'qr|gunicorn'

# يعرض WorkingDirectory و User و gunicorn --bind و --workers
systemctl cat qr_attendance
```

ثم من مجلد المشروع (`WorkingDirectory` أعلاه)، وبنفس الطريقة التي تحدّث بها الخادم عادة:

```bash
cd /opt/qr_attendance
git pull                      # بعد دمج فرع zkteco-device في main
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=qr_attendance.settings.production
python manage.py migrate      # يضيف رقم جهاز البصمة + جدولي الأجهزة والبصمات
sudo systemctl restart qr_attendance
sudo systemctl status qr_attendance
```

- **لا توجد حزم جديدة** في `requirements.txt` ولا قيم جديدة في `.env`.
- **لا حاجة لتغيير عدد الـ workers** (6 مناسبة). الجهاز يرسل طلباً كل 10 ثوانٍ تقريباً.
- تأكد أن `ALLOWED_HOSTS` في `.env` يحتوي `192.168.1.6` (غالباً موجود لأن المتصفحات تفتح النظام بهذا العنوان):

```bash
grep ALLOWED_HOSTS /opt/qr_attendance/.env
```

---

## 2. التأكد من المنفذ 80 | Check port 80

الموظفون يفتحون النظام على `http://192.168.1.6` بدون رقم منفذ، أي على المنفذ 80. الجهاز سيستخدم نفس المنفذ، لذلك **لا تحتاج قاعدة جدار ناري جديدة**.
Staff open the system on port 80, and the device will use the same port, so no new firewall rule is needed.

اعرف ما الذي يخدم المنفذ 80:

```bash
sudo ss -tlnp | grep -E ':80 |:8000 '
sudo iptables -t nat -S PREROUTING | grep -- '--dport 80'
```

- **إذا ظهر `REDIRECT --to-ports 8000`**: المنفذ 80 يُحوَّل إلى gunicorn، و`/iclock/` سيعمل كما هو.
- **إذا ظهر nginx على :80**: تأكد أن إعداد الموقع يمرر كل المسارات إلى gunicorn، أي يحتوي `location / { proxy_pass http://127.0.0.1:8000; ... }`. إذا كان يمرر مسارات محددة فقط، أضف:

  ```nginx
  location /iclock/ {
      proxy_pass http://127.0.0.1:8000;
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $remote_addr;
  }
  ```
  ثم `sudo nginx -t && sudo systemctl reload nginx`.

**اختبار من لابتوب على نفس الشبكة** (وليس من الخادم نفسه، لأن تحويل iptables لا يُطبق على الاتصالات المحلية):

```bash
curl -i http://192.168.1.6/iclock/cdata
```

النتيجة المتوقعة | Expected:

```
HTTP/1.1 400 Bad Request
...
ERROR: missing or invalid SN
```

هذه النتيجة تعني أن المسار يصل إلى النظام. أما `404` أو "Connection refused" فتعني أن الكود لم يُحدَّث أو أن المنفذ 80 لا يصل إلى gunicorn.

**الجدار الناري:** المتصفحات تصل للمنفذ 80 الآن، فالجهاز سيصل أيضاً **إذا كان على نفس الشبكة 192.168.1.x** (القسم 3). إذا كانت قواعدك تسمح لـ `192.168.1.0/24` فقط فلن يصل جهاز على `192.168.0.x`. للتحقق:

```bash
sudo ufw status verbose
sudo iptables -S INPUT
```

---

## 3. شبكة الجهاز | Device network

**المشكلة الحالية:** الجهاز على `192.168.0.101` (البوابة `192.168.0.1`) والخادم على `192.168.1.6`. هاتان شبكتان مختلفتان، ولن يصل الجهاز للخادم إلا إذا كان الراوتر يوجّه بينهما، وهذا غير مُعد غالباً.
**Current problem:** the device is on 192.168.0.x and the server on 192.168.1.x. These are different networks, so the device can't reach the server unless the router routes between them.

### الحالة أ (الأرجح): كابل الجهاز على نفس الراوتر/السويتش الذي عليه الخادم

غيّر عنوان الجهاز إلى عنوان فارغ في `192.168.1.x`.

**1) اعرف البوابة الصحيحة**، من الخادم:

```bash
ip route | grep default
# مثال: default via 192.168.1.1 dev eth0  ← البوابة = 192.168.1.1
```

**2) اختر عنواناً غير مستخدم**، مثلاً `192.168.1.201`. يفضل أن يكون خارج نطاق DHCP في الراوتر حتى لا يُعطى لجهاز آخر:

```bash
ping -c 3 192.168.1.201       # لا يوجد رد = غالباً فارغ
```

**3) على الجهاز:** `M/OK` ← **Comm.** ← **Ethernet**:

| الإعداد | القيمة الحالية | القيمة الجديدة |
|---|---|---|
| IP Address | 192.168.0.101 | **192.168.1.201** |
| Subnet Mask | 255.255.255.0 | 255.255.255.0 (كما هو) |
| Gateway | 192.168.0.1 | **192.168.1.1** (من `ip route`) |
| DNS | 0.0.0.0 | 0.0.0.0 (كما هو، غير مستخدم) |
| TCP COMM.Port | 4370 | 4370 (كما هو، غير مستخدم) |
| DHCP | OFF | OFF |

> يمكن بدلاً من ذلك تشغيل **DHCP = ON** ليأخذ الجهاز عنواناً تلقائياً من الراوتر، لأن الخادم لا يحتاج معرفة عنوان الجهاز. لكن العنوان الثابت أسهل في التشخيص.

**4) تحقق** من الخادم بعد الحفظ:

```bash
ping -c 4 192.168.1.201
```

### الحالة ب: الجهاز موصول براوتر آخر (شبكة 192.168.0.x منفصلة)

- **الأسهل:** انقل كابل الجهاز إلى سويتش/راوتر شبكة الخادم، ثم طبّق الحالة أ.
- **البديل:** إعداد توجيه (routing) بين الراوترين يسمح لـ `192.168.0.101` بالوصول إلى `192.168.1.6:80`. هذا يتم من إعدادات الراوتر وليس من النظام.

---

## 4. إعداد الخادم على الجهاز | Cloud Server Setting

على الجهاز: `M/OK` ← **Comm.** ← **Cloud Server Setting**:

| الإعداد | القيمة الحالية | القيمة الجديدة |
|---|---|---|
| Server Mode | ADMS | ADMS (كما هو) |
| Enable Domain Name | OFF | OFF |
| Server Address | 0.0.0.0 | **192.168.1.6** |
| Server Port | 8081 | **80** |
| Enable Proxy Server | OFF | OFF |

احفظ واخرج بـ `ESC`. إذا طلب الجهاز إعادة التشغيل فوافق، أو افصل الكهرباء ثم أعدها.

> لماذا 80 وليس 8081؟ لأن المنفذ 80 مفتوح ويصل للنظام الآن. المنفذ 8081 يحتاج قاعدة جدار ناري وتحويلاً جديداً بلا فائدة.

---

## 5. التاريخ والوقت | Date & time

الخادم يستخدم **وقت البصمة من الجهاز**، لذلك يجب أن تكون ساعة الجهاز صحيحة.
The server uses the device's punch time, so the device clock must be right.

`M/OK` ← **System** ← **Date Time**: اضبط التاريخ والوقت بالضبط، وتنسيق 24 ساعة. راجع إعداد التوقيت الصيفي (Daylight Saving) إن وجد بحيث يطابق وقت مصر.

- البصمة التي يكون وقتها **بعد الآن بأكثر من 10 دقائق** أو **أقدم من 30 يوماً** تُرفض وتظهر في السجل بنتيجة "وقت الجهاز غير منطقي".
- راجع الساعة بعد انقطاع الكهرباء الطويل ومرة شهرياً.

---

## 6. اعتماد الجهاز | Approve the device

عند أول اتصال يُسجَّل الجهاز تلقائياً **غير مفعّل**، ولا تُقبل بصماته حتى تعتمده. هذا يمنع أي جهاز غريب على الشبكة من تسجيل حضور.
On first contact the device registers itself as inactive. Its punches are refused until you approve it.

1. بعد القسم 4 بدقيقة تقريباً افتح `http://192.168.1.6/admin/` وسجل الدخول بحساب مدير Django (الحساب الذي أُنشئ بـ `seed_admin` أو `createsuperuser`).
2. **Attendance** ← **Biometric devices**: ستجد صفاً بالرقم التسلسلي للجهاز.
3. تحقق أن الرقم التسلسلي يطابق الجهاز: `M/OK` ← **System Info** ← **Device Info** ← **Serial Number**.
4. فعّل **Is active**، واكتب اسماً مثل "جهاز المدخل"، ثم **Save**.

- عمود **Last seen at** يتحدث كل 10 ثوانٍ تقريباً ما دام الجهاز متصلاً. هذا أسرع اختبار للاتصال.
- **إذا لم يظهر أي صف:** الجهاز لا يصل للخادم. راجع [استكشاف الأخطاء](#9-استكشاف-الأخطاء--troubleshooting).
- بعد الاعتماد يرسل الجهاز البصمات المخزنة فيه. ستظهر في **Device punches** بنتيجة "رقم بصمة غير مرتبط بمعلم"، وهذا طبيعي (انظر "الترتيب مهم" أعلاه).

> لا يوجد حساب Django admin؟ أنشئه على الخادم:
> ```bash
> cd /opt/qr_attendance && source venv/bin/activate
> export DJANGO_SETTINGS_MODULE=qr_attendance.settings.production
> python manage.py seed_admin
> ```

---

## 7. تسجيل المعلمين | Enroll teachers

لكل معلم سيستخدم الجهاز:

**أ) في النظام:** بوابة الإدارة ← **المعلمون** ← **تعديل** المعلم ← حقل **"رقم جهاز البصمة"** ← اكتب رقماً، مثلاً `1`، `2`، `3`... ← **حفظ**.
- الرقم أرقام فقط، من 1 حتى 999999999، ولا يتكرر بين معلمين (النموذج يرفض التكرار).
- يظهر الرقم في قائمة المعلمين بجانب كود المعلم مع أيقونة بصمة.
- الكورسات ("هذا كورس") لا تحتاج رقماً.

**ب) على الجهاز:** `M/OK` ← **User Mgt.** ← **New User**:

| الحقل | القيمة |
|---|---|
| User ID | **نفس "رقم جهاز البصمة"** في النظام |
| Name | اسم المعلم (اختياري، للعرض على الشاشة فقط) |
| User Role | Normal User |
| Fingerprint | ضع الإصبع 3 مرات. يُنصح بتسجيل إصبعين (إصبع احتياطي) |

احفظ بـ `M/OK`.

- **إذا كان المعلمون مسجلين على الجهاز من قبل:** افتح **User Mgt.** ← **All Users**، واكتب لكل معلم في النظام نفس الـ User ID الموجود على الجهاز، ولا داعي لإعادة تسجيل البصمة.
- الأصفار في البداية لا تهم: `0105` على الجهاز = `105` في النظام.
- **احمِ قائمة الجهاز:** سجّل نفسك على الجهاز برقم كبير لا يُستخدم للمعلمين (مثلاً `9001`) بدور **Super Admin**، حتى لا يستطيع أحد غيرك فتح الإعدادات. بصمات هذا الرقم تظهر في السجل كـ"غير مرتبط" فقط.
- عند ترك معلم للعمل: ألغِ تفعيله في النظام (بصماته تُسجَّل في السجل كـ"معلم غير نشط" ولا تُحتسب)، واحذفه من الجهاز. لا تعطِ رقمه لمعلم آخر قبل حذفه من الجهاز.

---

## 8. تجربة كاملة | End-to-end test

1. معلم له رقم يضع إصبعه، فيعرض الجهاز اسمه أو رقمه و"تم التحقق".
2. خلال ثوانٍ: Django admin ← **Device punches** ← صف جديد بالنتيجة **"تم تسجيل الحضور"**.
3. بوابة الإدارة ← سجلات حضور المعلمين: يظهر وقت الحضور.
4. انتظر **5 دقائق أو أكثر** ثم بصمة ثانية، فتظهر **"تم تسجيل المغادرة"** ويظهر وقت الانصراف ومدة الحضور.
5. بصمة ثالثة تظهر بالنتيجة "مغادرة مسجلة مسبقاً" ولا تغيّر شيئاً.

**متابعة مباشرة على الخادم** | Live logs on the server:

```bash
# طلبات الجهاز (نبض كل ~10 ثوانٍ + رفع البصمات)
tail -f /opt/qr_attendance/logs/access.log | grep iclock

# نتيجة كل بصمة
tail -f /opt/qr_attendance/logs/django.log | grep -i "device"
# مثال: Device CQZ7232460123 punch: user 105 at 2026-10-28 08:01:12+03:00 -> checked_in
```

> مسارات السجلات حسب `systemctl cat qr_attendance`: `--access-logfile` و`--error-logfile`، و`logs/django.log` داخل مجلد المشروع.

---

## 9. استكشاف الأخطاء | Troubleshooting

### الجهاز لا يظهر في Biometric devices أو Last seen لا يتحدث

الجهاز لا يصل للخادم. افحص بالترتيب:

1. `ping -c 4 192.168.1.201` من الخادم. إذا لم يرد: مشكلة شبكة (القسم 3).
2. Cloud Server Setting: العنوان `192.168.1.6` والمنفذ `80` و Server Mode = ADMS (القسم 4)، ثم أعد تشغيل الجهاز.
3. `curl -i http://192.168.1.6/iclock/cdata` من لابتوب يرجع `400 ... missing or invalid SN` (القسم 2).
4. `grep iclock /opt/qr_attendance/logs/access.log | tail`: إذا لم يظهر شيء فالطلبات لا تصل أصلاً (شبكة أو جدار ناري).

### طلبات الجهاز ترجع 403

الجهاز غير معتمد، فعّل **Is active** (القسم 6). البصمات لا تضيع: الجهاز يحتفظ بها ويعيد إرسالها بعد الاعتماد.

### نتائج البصمات في Device punches

| النتيجة | المعنى | الحل |
|---|---|---|
| تم تسجيل الحضور / تم تسجيل المغادرة | تم بنجاح | — |
| مسح مكرر خلال 5 دقائق من الحضور | بصمة ثانية بسرعة | طبيعي، تُتجاهل |
| مغادرة مسجلة مسبقاً | بصمة بعد الانصراف | طبيعي، تُتجاهل (نفس المحطة) |
| مسجل غياب بإذن لهذا اليوم | اليوم مسجل غياب بإذن | إذا حضر المعلم فعلاً: صحّح السجل يدوياً (انظر أسفل الجدول) |
| وقت المسح قبل وقت الحضور | وقت البصمة أقدم من حضور مسجل | راجع ساعة الجهاز |
| رقم بصمة غير مرتبط بمعلم | لا يوجد معلم بهذا الرقم | اكتب الرقم في "رقم جهاز البصمة" للمعلم. البصمات السابقة لا تُعاد معالجتها، فصحّحها يدوياً |
| معلم غير نشط | المعلم ملغى تفعيله | فعّله إذا كان ما زال يعمل |
| وقت الجهاز غير منطقي | وقت البصمة في المستقبل أو أقدم من 30 يوماً | اضبط ساعة الجهاز (القسم 5) |
| خطأ أثناء المعالجة | خطأ برمجي | انظر `logs/django.log` وأرسل الخطأ للمطور |

**التصحيح اليدوي | Manual fix:** بوابة الإدارة تعدّل التقييم والملاحظات فقط. لتعديل أوقات الحضور والانصراف استخدم Django admin: `http://192.168.1.6/admin/` ← **Teacher attendance records** ← افتح سجل المعلم في ذلك اليوم (أو **Add**) ← عدّل **Check in time** و**Check out time** و**Record type** ← **Save**. وقت البصمة الأصلي موجود في **Device punches**.

### `DisallowedHost` في سجل الأخطاء

أضف العنوان الظاهر في الخطأ إلى `ALLOWED_HOSTS` في `.env` ثم `sudo systemctl restart qr_attendance`.

### الأوقات مزاحة بساعة أو ساعتين

- ساعة الجهاز أو إعداد التوقيت الصيفي فيه غير صحيح (القسم 5).
- `TIME_ZONE` في `.env` يجب أن يكون `Africa/Cairo`.

### سجل الوصول يظهر `404` لمسارات مثل `/iclock/registry` أو `/iclock/push`

نسخة برنامج الجهاز تستخدم إصداراً أحدث من بروتوكول Push غير مدعوم حالياً. أرسل هذه الأسطر للمطور.

### هل تضيع البصمات إذا توقف الخادم؟

لا. الجهاز يخزن البصمات ويرسلها عند عودة الخادم، وتُسجَّل بوقتها الأصلي. وإذا أُرسلت البصمة مرتين لا تُحتسب مرتين.

---

## ملاحظات أمنية | Security notes

- مسارات `/iclock/` لا تستخدم كلمة مرور، لأن الجهاز لا يستطيع تسجيل الدخول. الحماية أن **الأجهزة المعتمدة فقط** (بالرقم التسلسلي) تُقبل بصماتها.
- أبقِ الخادم على الشبكة الداخلية فقط، ولا تفتح المنفذ 80 للإنترنت.
- راجع **Biometric devices** أحياناً: أي صف جديد لم تضفه أنت يعني جهازاً آخر يحاول الاتصال. اتركه غير مفعّل أو احذفه.

---

## ملخص تقني | Technical summary

| الملف | الوظيفة |
|---|---|
| `attendance/iclock.py` | مسارات بروتوكول ADMS: `cdata` و`getrequest` و`devicecmd` و`ping` |
| `attendance/iclock_urls.py` | ربطها على `/iclock/` |
| `attendance/services.py` | `record_teacher_scan()`: قواعد الحضور/الانصراف المشتركة بين المحطة والجهاز |
| `attendance/models.py` | `BiometricDevice` (الأجهزة) و`DevicePunch` (سجل البصمات) و`TeacherScanOutcome` |
| `core/models.py` | `Teacher.device_user_id` (رقم جهاز البصمة) |
| `admin_portal/forms.py` | حقل "رقم جهاز البصمة" في نموذج المعلم |

ردود الخادم على الجهاز | Server replies:

| طلب الجهاز | الرد |
|---|---|
| `GET /iclock/cdata?SN=…&options=all` | `GET OPTION FROM: <SN>` + الإعدادات (`Realtime=1`, `Delay=10`, `TransFlag=TransData AttLog`, …) |
| `POST /iclock/cdata?SN=…&table=ATTLOG` | `OK: <عدد الأسطر المقبولة>` |
| `POST /iclock/cdata?SN=…&table=<أخرى>` | `OK` |
| `GET /iclock/getrequest?SN=…` | `OK` (لا أوامر) |
| `POST /iclock/devicecmd?SN=…` | `OK` |
| جهاز غير معتمد | `403 ERROR: device not approved` (الجهاز يعيد المحاولة لاحقاً) |

الاختبارات | Tests: `attendance/tests/test_device.py` و`admin_portal/tests/test_teacher_device_id.py`.
