import os
import django
import random
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qr_attendance.settings')
django.setup()

from core.models import User, Student, Teacher, StudentTeacherLink, CoursePayment

def run():
    print("Seeding course data...")
    
    # Create an admin if none exists
    if not User.objects.filter(role=User.Role.ADMIN).exists():
        User.objects.create_user(phone='01000000000', password='password', role=User.Role.ADMIN)

    # Create a course
    user, _ = User.objects.get_or_create(phone='01555555555', defaults={'role': User.Role.TEACHER})
    if not hasattr(user, 'teacher'):
        user.set_password('password')
        user.save()
        course = Teacher.objects.create(
            user=user,
            full_name="كورس الفيزياء المكثف",
            is_course=True,
            subject="فيزياء",
            teacher_code="PHY-101"
        )
    else:
        course = user.teacher
        course.is_course = True
        course.save()

    print(f"Course: {course.full_name}")

    # Create 5 students and link them
    students = []
    for i in range(1, 6):
        phone = f"012000000{i:02d}"
        s_user, _ = User.objects.get_or_create(phone=phone, defaults={'role': User.Role.STUDENT})
        s_user.set_password('password')
        s_user.save()
        
        student, created = Student.objects.get_or_create(
            user=s_user,
            defaults={
                'full_name': f"طالب فيزياء {i}",
                'grade': "الصف الثالث الثانوي",
                'parent_phone': f"011000000{i:02d}"
            }
        )
        students.append(student)
        
        StudentTeacherLink.objects.get_or_create(
            student=student,
            teacher=course,
            defaults={'is_primary': False}
        )

    print(f"Created {len(students)} students and linked them to the course.")

    # Seed past payments
    today = date.today()
    if today.month == 1:
        last_month = 12
        last_month_year = today.year - 1
    else:
        last_month = today.month - 1
        last_month_year = today.year
    
    CoursePayment.objects.filter(course=course).delete() # clean up
    
    print(f"Seeding payments for {last_month_year}-{last_month}...")
    for i, student in enumerate(students):
        status = random.choice([CoursePayment.PaymentStatus.PAID, CoursePayment.PaymentStatus.PARTIAL, CoursePayment.PaymentStatus.NOT_PAID])
        amount = 500 if status == CoursePayment.PaymentStatus.PAID else (250 if status == CoursePayment.PaymentStatus.PARTIAL else 0)
        CoursePayment.objects.create(
            student=student,
            course=course,
            year=last_month_year,
            month=last_month,
            status=status,
            amount_paid=amount,
            note="مدفوعات الشهر الماضي" if amount > 0 else ""
        )

    # Seed some current month payments
    print(f"Seeding payments for {today.year}-{today.month}...")
    # Student 1: Paid
    CoursePayment.objects.create(
        student=students[0], course=course, year=today.year, month=today.month,
        status=CoursePayment.PaymentStatus.PAID, amount_paid=500, note="دفع مبكر"
    )
    # Student 2: Partial
    CoursePayment.objects.create(
        student=students[1], course=course, year=today.year, month=today.month,
        status=CoursePayment.PaymentStatus.PARTIAL, amount_paid=200, note="باقي 300"
    )
    # Others: Not Paid (no record needed, handled by UI, but we can create NOT_PAID explicitly)

    print("Data seeding completed!")

if __name__ == '__main__':
    run()
