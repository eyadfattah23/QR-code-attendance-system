import re

from django import forms
from django.db import transaction

from core.models import Student, Teacher, User


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['full_name', 'national_id', 'student_code', 'grade']
        labels = {
            'full_name': 'الاسم الكامل',
            'national_id': 'الرقم القومي / رقم التسجيل',
            'student_code': 'كود الطالب',
            'grade': 'الصف / المستوى',
        }
        help_texts = {
            'student_code': 'اختياري — يُملأ تلقائياً من الرقم القومي إن تُرك فارغاً',
            'grade': 'مثال: السنة الأولى، المستوى 5',
        }
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'national_id': forms.TextInput(attrs={'class': 'form-control'}),
            'student_code': forms.TextInput(attrs={'class': 'form-control'}),
            'grade': forms.TextInput(attrs={'class': 'form-control'}),
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
            self.instance.save()
            teacher = self.instance
        return teacher
