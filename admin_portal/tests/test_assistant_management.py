from django.test import TestCase, Client
from django.urls import reverse
from core.models import User, Teacher, AssistantTeacherLink

class AssistantManagementTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_user(
            phone='01000000000', password='pass', role=User.Role.ADMIN
        )
        cls.assistant_user = User.objects.create_user(
            phone='01000000001', password='pass', role=User.Role.ASSISTANT, first_name='Test Assistant'
        )
        cls.teacher1 = Teacher.objects.create(
            user=User.objects.create_user(phone='01100000001', password='pass', role=User.Role.TEACHER),
            full_name='Teacher 1'
        )
        cls.teacher2 = Teacher.objects.create(
            user=User.objects.create_user(phone='01100000002', password='pass', role=User.Role.TEACHER),
            full_name='Teacher 2'
        )

    def setUp(self):
        self.client = Client()
        self.client.login(phone='01000000000', password='pass')

    def test_assistant_list(self):
        url = reverse('admin_portal:assistant_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Assistant')

    def test_assistant_create(self):
        url = reverse('admin_portal:assistant_create')
        response = self.client.post(url, {
            'full_name': 'New Assistant',
            'phone': '01000000002',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(phone='01000000002', role=User.Role.ASSISTANT).exists())

    def test_assistant_edit(self):
        url = reverse('admin_portal:assistant_edit', args=[self.assistant_user.pk])
        response = self.client.post(url, {
            'full_name': 'Updated Assistant',
            'phone': '01000000001',
            'password': ''
        })
        self.assertEqual(response.status_code, 302)
        self.assistant_user.refresh_from_db()
        self.assertEqual(self.assistant_user.first_name, 'Updated Assistant')

    def test_assistant_links(self):
        url = reverse('admin_portal:assistant_links', args=[self.assistant_user.pk])
        # Link to teacher1 only
        response = self.client.post(url, {
            'teachers': [self.teacher1.id]
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AssistantTeacherLink.objects.filter(user=self.assistant_user, teacher=self.teacher1).exists())
        self.assertFalse(AssistantTeacherLink.objects.filter(user=self.assistant_user, teacher=self.teacher2).exists())
        
        # Link to both
        response = self.client.post(url, {
            'teachers': [self.teacher1.id, self.teacher2.id]
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AssistantTeacherLink.objects.filter(user=self.assistant_user).count(), 2)
        
        # Link to none
        response = self.client.post(url, {
            'teachers': []
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AssistantTeacherLink.objects.filter(user=self.assistant_user).count(), 0)

    def test_assistant_delete(self):
        url = reverse('admin_portal:assistant_delete', args=[self.assistant_user.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.assistant_user.pk).exists())
