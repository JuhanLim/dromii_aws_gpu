from django.db import models
from django.utils import timezone

class Instance(models.Model):
    instance_id = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    instance_type = models.CharField(max_length=20)
    state = models.CharField(max_length=20)
    restart_attempts = models.IntegerField(default=0)
    auto_restart_enabled = models.BooleanField(default=False)
    last_restart_attempt = models.DateTimeField(null=True, blank=True)