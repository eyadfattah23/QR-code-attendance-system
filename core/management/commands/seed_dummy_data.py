import random
import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from core.models import User, Teacher, Student, StudentTeacherLink
from attendance.models import TeacherAttendanceRecord, StudentAttendanceRecord

class Command(BaseCommand):
    help = 'Seed dummy data for testing (Teachers, Students, Attendance)'

    def add_arguments(self, parser):
        parser.add_argument('--teachers', type=int, default=5, help='Number of teachers to create')
        parser.add_argument('--students', type=int, default=30, help='Number of students to create')
        parser.add_argument('--days', type=int, default=10, help='Number of past days to generate attendance for')

    @transaction.atomic
    def handle(self, *args, **kwargs):
        num_teachers = kwargs['teachers']
        num_students = kwargs['students']
        num_days = kwargs['days']

        self.stdout.write(self.style.WARNING(f'Seeding {num_teachers} teachers, {num_students} students, and {num_days} days of attendance...'))

        # Seed Teachers
        teachers = []
        for i in range(num_teachers):
            phone = f'010{random.randint(10000000, 99999999)}'
            first_name = random.choice(['أحمد', 'محمد', 'علي', 'عمر', 'خالد', 'فاطمة', 'عائشة', 'مريم'])
            last_name = random.choice(['محمود', 'حسن', 'ابراهيم', 'يوسف', 'مصطفى', 'عبدالله'])
            full_name = f'{first_name} {last_name} {random.choice(["سعيد", "صالح", "عباس"])}'
            
            user, created = User.objects.get_or_create(
                phone=phone,
                defaults={
                    'role': User.Role.TEACHER,
                    'first_name': first_name,
                    'last_name': last_name,
                }
            )
            if created:
                user.set_password('123456')
                user.save()
            
            teacher, t_created = Teacher.objects.get_or_create(
                user=user,
                defaults={
                    'full_name': full_name,
                    'subject': random.choice(['القرآن الكريم', 'التجويد', 'العقيدة', 'الفقه']),
                    'gender': random.choice(['M', 'F']),
                }
            )
            teachers.append(teacher)
            self.stdout.write(f'Created teacher: {full_name}')

        # Seed Students
        students = []
        for i in range(num_students):
            first_name = random.choice(['عمر', 'ياسين', 'آدم', 'يوسف', 'سيف', 'يمنى', 'حبيبة', 'جنى', 'ملك'])
            last_name = random.choice(['محمد', 'أحمد', 'حسن', 'عبدالرحمن', 'طارق', 'سعيد'])
            full_name = f'{first_name} {last_name} {random.choice(["محمود", "كمال", "سالم"])} {i}'
            national_id = f'3{random.randint(1000000000000, 9999999999999)}'
            
            student, s_created = Student.objects.get_or_create(
                national_id=national_id,
                defaults={
                    'full_name': full_name,
                    'student_code': f'STU{random.randint(1000, 9999)}',
                    'grade': random.choice(['الصف الأول', 'الصف الثاني', 'الصف الثالث', 'الصف الرابع']),
                    'gender': random.choice(['M', 'F']),
                    'parent_phone': f'011{random.randint(10000000, 99999999)}',
                    'parent_full_name': f'{last_name} {random.choice(["محمود", "كمال", "سالم"])}',
                }
            )
            students.append(student)

            # Link to a random teacher
            t = random.choice(teachers)
            StudentTeacherLink.objects.get_or_create(
                student=student,
                teacher=t
            )

        self.stdout.write(f'Created {len(students)} students and linked them to teachers.')

        # Seed Attendance
        today = timezone.localdate()
        for i in range(num_days):
            current_date = today - timedelta(days=i)
            # Skip Fridays and Saturdays (assuming weekend, just to make data realistic)
            if current_date.weekday() in [4, 5]:
                continue
                
            # Teacher Attendance
            for t in teachers:
                # 80% chance of attendance
                if random.random() < 0.8:
                    check_in = timezone.make_aware(timezone.datetime.combine(current_date, timezone.datetime.min.time())) + timedelta(hours=random.randint(7, 8), minutes=random.randint(0, 59))
                    check_out = check_in + timedelta(hours=random.randint(4, 7), minutes=random.randint(0, 59))
                    
                    TeacherAttendanceRecord.objects.get_or_create(
                        teacher=t,
                        date=current_date,
                        defaults={
                            'check_in_time': check_in,
                            'check_out_time': check_out if random.random() < 0.9 else None, # 10% forget to check out
                            'rating': random.randint(7, 10),
                            'notes': random.choice(['', '', 'حضور مبكر', 'تأخير بسيط']),
                        }
                    )

            # Student Attendance
            for s in students:
                # 85% chance of attendance
                if random.random() < 0.85:
                    check_in = timezone.make_aware(timezone.datetime.combine(current_date, timezone.datetime.min.time())) + timedelta(hours=random.randint(7, 9), minutes=random.randint(0, 59))
                    check_out = check_in + timedelta(hours=random.randint(3, 6), minutes=random.randint(0, 59))
                    
                    link = s.teacher_links.first()
                    original_t = link.teacher if link else random.choice(teachers)
                    
                    assigned_t = original_t
                    # 10% chance of substitute teacher
                    if random.random() < 0.1:
                        assigned_t = random.choice(teachers)
                        
                    StudentAttendanceRecord.objects.get_or_create(
                        student=s,
                        date=current_date,
                        defaults={
                            'check_in_time': check_in,
                            'check_out_time': check_out if random.random() < 0.95 else None,
                            'original_teacher': original_t,
                            'assigned_teacher': assigned_t,
                            'rating': random.randint(5, 10),
                            'substitute_note': 'نيابة عن المعلم الأساسي' if assigned_t != original_t else '',
                        }
                    )
                    
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {num_days} days of attendance records!'))
