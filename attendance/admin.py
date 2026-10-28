from django.contrib import admin

from .models import (
    BiometricDevice,
    DevicePunch,
    StudentAttendanceRecord,
    TeacherAttendanceRecord,
)


@admin.register(StudentAttendanceRecord)
class StudentAttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'date',
        'check_in_time',
        'assigned_teacher',
        'original_teacher',
        'rating',
    )
    list_filter = ('date', 'assigned_teacher', 'original_teacher', 'rating')
    search_fields = ('student__full_name', 'student__national_id')
    readonly_fields = ('created_at',)


@admin.register(TeacherAttendanceRecord)
class TeacherAttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'date', 'check_in_time', 'recorded_by')
    list_filter = ('date', 'teacher')
    search_fields = ('teacher__full_name',)
    readonly_fields = ('created_at',)


@admin.register(BiometricDevice)
class BiometricDeviceAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'name', 'is_active', 'last_seen_at', 'last_ip')
    list_editable = ('name', 'is_active')
    readonly_fields = ('last_seen_at', 'last_ip', 'created_at')


@admin.register(DevicePunch)
class DevicePunchAdmin(admin.ModelAdmin):
    """Read-only log of every punch the devices sent, for checking what happened."""

    list_display = ('punch_time', 'device_user_id', 'teacher', 'result', 'verify_type', 'device')
    list_filter = ('result', 'device', 'punch_time')
    search_fields = ('device_user_id', 'teacher__full_name')
    date_hierarchy = 'punch_time'
    list_select_related = ('teacher', 'device')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
