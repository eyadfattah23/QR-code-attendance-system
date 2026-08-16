import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qr_attendance.settings.development')
django.setup()

from core.models import User, Teacher, Student, StudentTeacherLink, AssistantTeacherLink

def run():
    print("Seeding Phase 4 test data...")

    # 1. Admin User
    admin, _ = User.objects.get_or_create(
        phone='01000000001',
        defaults={'role': User.Role.ADMIN, 'first_name': 'Admin', 'last_name': 'User'}
    )
    if _:
        admin.set_password('adminpass123')
        admin.save()
        print("- Created Admin: 01000000001 / adminpass123")

    # 2. Supervisor User
    supervisor, _ = User.objects.get_or_create(
        phone='01000000002',
        defaults={'role': User.Role.SUPERVISOR, 'first_name': 'Super', 'last_name': 'Visor'}
    )
    if _:
        supervisor.set_password('superpass123')
        supervisor.save()
        print("- Created Supervisor: 01000000002 / superpass123")

    # 3. Teacher 1 (Linked to Assistant)
    t1_user, _ = User.objects.get_or_create(
        phone='01000000003',
        defaults={'role': User.Role.TEACHER, 'first_name': 'Tariq', 'last_name': 'Teacher'}
    )
    if _:
        t1_user.set_password('teacherpass123')
        t1_user.save()
        
    t1, _ = Teacher.objects.get_or_create(
        user=t1_user,
        defaults={'full_name': 'Tariq Teacher', 'subject': 'Math', 'is_course': True}
    )
    print(f"- Teacher 1: {t1_user.phone} / teacherpass123 (Subject: {t1.subject})")

    # 4. Teacher 2 (Not Linked)
    t2_user, _ = User.objects.get_or_create(
        phone='01000000004',
        defaults={'role': User.Role.TEACHER, 'first_name': 'Nour', 'last_name': 'Teacher'}
    )
    if _:
        t2_user.set_password('teacherpass123')
        t2_user.save()

    t2, _ = Teacher.objects.get_or_create(
        user=t2_user,
        defaults={'full_name': 'Nour Teacher', 'subject': 'Science', 'is_course': False}
    )
    print(f"- Teacher 2: {t2_user.phone} / teacherpass123 (Subject: {t2.subject})")

    # 5. Assistant User
    assistant, _ = User.objects.get_or_create(
        phone='01000000005',
        defaults={'role': User.Role.ASSISTANT, 'first_name': 'Musaed', 'last_name': 'User'}
    )
    if _:
        assistant.set_password('assistpass123')
        assistant.save()
        print("- Created Assistant: 01000000005 / assistpass123")

    # Link Assistant to Teacher 1 ONLY
    AssistantTeacherLink.objects.get_or_create(user=assistant, teacher=t1)
    print("- Linked Assistant to Teacher 1")

    # 6. Students
    s1, _ = Student.objects.get_or_create(national_id='12345678901234', defaults={'full_name': 'Student One', 'student_code': 'STU001'})
    s2, _ = Student.objects.get_or_create(national_id='12345678901235', defaults={'full_name': 'Student Two', 'student_code': 'STU002'})
    
    StudentTeacherLink.objects.get_or_create(student=s1, teacher=t1, defaults={'is_primary': True})
    StudentTeacherLink.objects.get_or_create(student=s2, teacher=t1, defaults={'is_primary': True})
    StudentTeacherLink.objects.get_or_create(student=s2, teacher=t2, defaults={'is_primary': False})
    print("- Created students and linked to teachers")

    print("\n✅ Seed complete!")

if __name__ == '__main__':
    run()
