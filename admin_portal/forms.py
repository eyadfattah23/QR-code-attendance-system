import re

from django import forms
from django.db import transaction

from core.models import Student, Teacher, User, CoursePayment, StudentTeacherLink

GENDER_CHOICES = [
    ('', '— الكل —'),
    ('M', 'ذكر'),
    ('F', 'أنثى'),
]


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'full_name', 'nickname', 'national_id', 'student_code',
            'image', 'grade', 'gender', 'phone', 'parent_phone',
            'date_of_birth', 'joining_date', 'hall_name', 'notes',
            # Parent / Guardian
            'parent_full_name', 'parent_qualification', 'parent_job',
            'parent_calls_phone', 'parent_marital_status', 'parent_spouse_job',
            'parent_address', 'child_pickup_person',
        ]
        labels = {
            'full_name': 'الاسم الكامل',
            'nickname': 'اللقب / الاسم المختصر',
            'national_id': 'الرقم القومي / رقم التسجيل',
            'student_code': 'كود الطالب',
            'image': 'صورة الطالب',
            'grade': 'الصف / المستوى',
            'gender': 'الجنس',
            'phone': 'هاتف الطالب',
            'parent_phone': 'واتساب ولي الأمر',
            'date_of_birth': 'تاريخ الميلاد',
            'joining_date': 'تاريخ الانضمام',
            'hall_name': 'اسم القاعة',
            'notes': 'ملاحظات',
            'parent_full_name': 'الاسم الرباعي لولي الأمر',
            'parent_qualification': 'المؤهل الدراسي',
            'parent_job': 'الوظيفة الحالية',
            'parent_calls_phone': 'رقم المكالمات',
            'parent_marital_status': 'الحالة الاجتماعية',
            'parent_spouse_job': 'وظيفة الزوج / الزوجة',
            'parent_address': 'العنوان',
            'child_pickup_person': 'من يستلم الطفل',
        }
        help_texts = {
            'student_code': 'اختياري — يُملأ تلقائياً من الرقم القومي إن تُرك فارغاً',
            'grade': 'مثال: السنة الأولى، المستوى 5',
            'phone': 'اختياري — 11 رقماً يبدأ بـ 01',
            'parent_phone': 'اختياري — 11 رقماً يبدأ بـ 01',
            'parent_calls_phone': 'اختياري — 11 رقماً يبدأ بـ 01 (يمكن أن يكون نفس الواتساب)',
            'nickname': 'اختياري',
            'hall_name': 'اختياري',
            'notes': 'اختياري',
            'parent_spouse_job': 'اختياري',
            'child_pickup_person': 'اختياري',
        }
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'nickname': forms.TextInput(attrs={'class': 'form-control'}),
            'national_id': forms.TextInput(attrs={'class': 'form-control'}),
            'student_code': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'grade': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr', 'placeholder': '01XXXXXXXXX'}),
            'parent_phone': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr', 'placeholder': '01XXXXXXXXX'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'joining_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hall_name': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'parent_full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'parent_qualification': forms.TextInput(attrs={'class': 'form-control'}),
            'parent_job': forms.TextInput(attrs={'class': 'form-control'}),
            'parent_calls_phone': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr', 'placeholder': '01XXXXXXXXX'}),
            'parent_marital_status': forms.Select(attrs={'class': 'form-select'}),
            'parent_spouse_job': forms.TextInput(attrs={'class': 'form-control'}),
            'parent_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'child_pickup_person': forms.TextInput(attrs={'class': 'form-control'}),
        }
        error_messages = {
            'full_name': {
                'unique': 'يوجد طالب مسجل بهذا الاسم بالفعل. يرجى التحقق من الاسم.',
            },
        }


class TeacherForm(forms.Form):
    """Combined form for creating / editing a Teacher and its linked User account."""

    # --- Teacher profile ---
    full_name = forms.CharField(
        max_length=255,
        label='الاسم الكامل',
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'autofocus': True}),
    )
    subject = forms.CharField(
        max_length=100,
        required=False,
        label='المجموعة',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='اختياري',
    )
    teacher_code = forms.CharField(
        max_length=50,
        required=False,
        label='كود المعلم',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='كود تعريفي للمعلم',
    )
    gender = forms.ChoiceField(
        choices=[('', '— غير محدد —'), ('M', 'ذكر'), ('F', 'أنثى')],
        required=False,
        label='الجنس',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    is_course = forms.BooleanField(
        required=False,
        label='هذا كورس (وليس معلماً أساسياً)',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='فعّل هذا الخيار ليظهر في قائمة الكورسات بمحطة المسح',
    )
    description = forms.CharField(
        required=False,
        label='وصف / ملاحظات',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        help_text='اختياري — وصف الكورس أو ملاحظات إضافية',
    )

    # --- User account ---
    phone = forms.CharField(
        max_length=11,
        label='رقم الهاتف',
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
        help_text='11 رقم يبدأ بصفر (مثال: 01234567890)',
    )
    first_name = forms.CharField(
        max_length=150,
        required=False,
        label='الاسم الأول',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        label='الاسم الأخير',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    password = forms.CharField(
        required=False,
        label='كلمة المرور',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='اتركها فارغة عند التعديل للإبقاء على كلمة المرور الحالية',
    )

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance  # Teacher object when editing, None when creating
        if instance is None:
            self.fields['password'].required = True
            self.fields['password'].help_text = ''
        else:
            self.fields['gender'].initial = instance.gender or ''
            self.fields['teacher_code'].initial = instance.teacher_code or ''
            self.fields['is_course'].initial = instance.is_course
            self.fields['description'].initial = instance.description or ''

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if not re.match(r'^0\d{10}$', phone):
            raise forms.ValidationError(
                'رقم الهاتف يجب أن يكون 11 رقم ويبدأ بصفر (مثال: 01234567890)')
        qs = User.objects.filter(phone=phone)
        if self.instance:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('رقم الهاتف مستخدم بالفعل')
        return phone

    def clean_teacher_code(self):
        teacher_code = self.cleaned_data.get('teacher_code')
        if not teacher_code:
            return teacher_code
        qs = Teacher.objects.filter(teacher_code=teacher_code)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('كود المعلم مستخدم بالفعل')
        return teacher_code

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        if self.instance is None:
            user = User.objects.create_user(
                phone=data['phone'],
                password=data['password'],
                role=User.Role.TEACHER,
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
            )
            teacher = Teacher.objects.create(
                user=user,
                full_name=data['full_name'],
                subject=data.get('subject') or None,
                gender=data.get('gender') or None,
                teacher_code=data.get('teacher_code') or None,
                is_course=data.get('is_course', False),
                description=data.get('description', ''),
            )
        else:
            user = self.instance.user
            user.phone = data['phone']
            user.first_name = data.get('first_name', '')
            user.last_name = data.get('last_name', '')
            if data.get('password'):
                user.set_password(data['password'])
            user.save()

            self.instance.full_name = data['full_name']
            self.instance.subject = data.get('subject') or None
            self.instance.gender = data.get('gender') or None
            self.instance.teacher_code = data.get('teacher_code') or None
            self.instance.is_course = data.get('is_course', False)
            self.instance.description = data.get('description', '')
            self.instance.save()
            teacher = self.instance
        return teacher


class CoursePaymentForm(forms.ModelForm):
    """Form for creating / editing a CoursePayment record."""

    class Meta:
        model = CoursePayment
        fields = ['student', 'course', 'year', 'month', 'status', 'amount_paid', 'note']
        labels = {
            'student': 'الطالب',
            'course': 'الكورس',
            'year': 'السنة',
            'month': 'الشهر',
            'status': 'حالة الدفع',
            'amount_paid': 'المبلغ المدفوع',
            'note': 'ملاحظات',
        }
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'month': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'amount_paid': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get('student')
        course = cleaned.get('course')
        if student and course:
            if not StudentTeacherLink.objects.filter(
                student=student, teacher=course
            ).exists():
                raise forms.ValidationError(
                    'هذا الطالب غير مسجل في هذا الكورس. يجب ربطه أولاً.'
                )
        month = cleaned.get('month')
        if month is not None and (month < 1 or month > 12):
            raise forms.ValidationError('الشهر يجب أن يكون بين 1 و 12')
        return cleaned


class SupervisorForm(forms.Form):
    """Form for creating / editing a supervisor user account."""

    full_name = forms.CharField(
        max_length=255,
        label='الاسم الكامل',
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'autofocus': True}),
    )
    phone = forms.CharField(
        max_length=11,
        label='رقم الهاتف',
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
        help_text='11 رقم يبدأ بصفر',
    )
    password = forms.CharField(
        required=False,
        label='كلمة المرور',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='اتركها فارغة عند التعديل للإبقاء على كلمة المرور الحالية',
    )

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance  # User object when editing, None when creating
        if instance is None:
            self.fields['password'].required = True
            self.fields['password'].help_text = ''

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if not re.match(r'^0\d{10}$', phone):
            raise forms.ValidationError(
                'رقم الهاتف يجب أن يكون 11 رقم ويبدأ بصفر')
        qs = User.objects.filter(phone=phone)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('رقم الهاتف مستخدم بالفعل')
        return phone

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        if self.instance is None:
            user = User.objects.create_user(
                phone=data['phone'],
                password=data['password'],
                role=User.Role.SUPERVISOR,
                first_name=data['full_name'],
            )
        else:
            user = self.instance
            user.phone = data['phone']
            user.first_name = data['full_name']
            if data.get('password'):
                user.set_password(data['password'])
            user.save()
        return user
