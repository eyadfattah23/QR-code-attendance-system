from django.db import models


class AuditLog(models.Model):
    """Records every delete or edit action performed in the system."""

    class Action(models.TextChoices):
        DELETE = 'delete', 'حذف'
        EDIT = 'edit', 'تعديل'

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=10, choices=Action.choices)
    actor_phone = models.CharField(max_length=20)
    ip_address = models.CharField(max_length=45)   # supports IPv6
    object_type = models.CharField(max_length=60)  # e.g. "طالب", "سجل حضور"
    object_repr = models.CharField(max_length=255)  # e.g. student name / date

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'سجل المراجعة'
        verbose_name_plural = 'سجلات المراجعة'

    def __str__(self):
        return f"{self.get_action_display()} — {self.object_type}: {self.object_repr} ({self.actor_phone})"
