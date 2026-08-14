from core.models import Student, Teacher, StudentTeacherLink
from django.contrib.auth import get_user_model

User = get_user_model()

def seed():
    # 1. Create Users
    user1, _ = User.objects.get_or_create(phone="0790000001", defaults={"password": "pbkdf2_sha256$600000$...", "role": User.Role.TEACHER})
    user2, _ = User.objects.get_or_create(phone="0790000002", defaults={"password": "pbkdf2_sha256$600000$...", "role": User.Role.TEACHER})
    
    # 2. Create Teachers
    teacher_ahmad, _ = Teacher.objects.get_or_create(user=user1, defaults={"full_name": "أستاذ أحمد (عادي)", "teacher_code": "T-AHMAD", "is_course": False})
    teacher_math, _ = Teacher.objects.get_or_create(user=user2, defaults={"full_name": "دورة الرياضيات", "teacher_code": "C-MATH", "is_course": True})
    
    # 3. Create Students
    student1, _ = Student.objects.get_or_create(student_code="S-001", defaults={"full_name": "طالب 1 (أساسي عند أحمد)", "national_id": "1111111111"})
    student2, _ = Student.objects.get_or_create(student_code="S-002", defaults={"full_name": "طالب 2 (غير مسجل بحلقات)", "national_id": "2222222222"})
    
    # 4. Link Student 1 to Teacher Ahmad
    StudentTeacherLink.objects.get_or_create(student=student1, teacher=teacher_ahmad, defaults={"is_primary": True})
    
    print("Seeding Complete!")
    print(f"Teacher 1 (Normal): {teacher_ahmad.full_name} | Code: {teacher_ahmad.teacher_code}")
    print(f"Teacher 2 (Course): {teacher_math.full_name} | Code: {teacher_math.teacher_code}")
    print(f"Student 1: {student1.full_name} | Code: {student1.student_code} | Primary: {teacher_ahmad.full_name}")
    print(f"Student 2: {student2.full_name} | Code: {student2.student_code} | No Primary Link")

seed()
