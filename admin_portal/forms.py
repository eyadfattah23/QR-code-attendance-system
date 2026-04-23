from django import forms

from core.models import Student


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
