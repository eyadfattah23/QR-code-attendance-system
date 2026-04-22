from django.contrib import admin

from .models import StudentAttendanceRecord, TeacherAttendanceRecord


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
