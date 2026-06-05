from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django import forms

from .models import User, Teacher, Student, StudentTeacherLink


# ---------------------------------------------------------------------------
# Custom forms for phone-based User
# ---------------------------------------------------------------------------

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('phone', 'first_name', 'last_name', 'email', 'role')


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


# ---------------------------------------------------------------------------
# User admin — create/edit admins and teachers
# ---------------------------------------------------------------------------

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ('phone', 'full_name', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('phone', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('المعلومات الشخصية', {
         'fields': ('first_name', 'last_name', 'email')}),
        ('الصلاحيات', {'fields': ('role', 'is_active', 'is_staff',
         'is_superuser', 'groups', 'user_permissions')}),
        ('التواريخ', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'first_name', 'last_name', 'email', 'role', 'password1', 'password2'),
        }),
    )

    def full_name(self, obj):
        return obj.get_full_name() or '—'
    full_name.short_description = 'الاسم'


# ---------------------------------------------------------------------------
# Teacher admin — link teacher profile to user
# ---------------------------------------------------------------------------

class TeacherInline(admin.StackedInline):
    model = Teacher
    extra = 0
    fields = ('full_name', 'subject', 'gender')
    can_delete = False


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'subject', 'gender', 'phone', 'student_count')
    list_filter = ('gender', 'subject')
    search_fields = ('full_name', 'subject', 'user__phone')
    autocomplete_fields = ('user',)

    def phone(self, obj):
        return obj.user.phone
    phone.short_description = 'رقم الهاتف'

    def student_count(self, obj):
        return obj.student_links.count()
    student_count.short_description = 'عدد الطلاب'
