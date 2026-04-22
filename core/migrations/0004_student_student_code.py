from django.db import migrations, models


def populate_student_code(apps, schema_editor):
    Student = apps.get_model('core', 'Student')
    for student in Student.objects.all():
        if not student.student_code:
            base_code = (student.national_id or '').strip().upper()
            if not base_code:
                base_code = f"S{str(student.id).replace('-', '')[:8].upper()}"

            code = base_code
            suffix = 1
            while Student.objects.exclude(pk=student.pk).filter(student_code=code).exists():
                suffix += 1
                code = f"{base_code}-{suffix}"

            student.student_code = code
            student.save(update_fields=['student_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_alter_user_managers'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='student_code',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Easy student ID for manual entry (e.g., STU1001)',
                max_length=30,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(populate_student_code, migrations.RunPython.noop),
    ]
