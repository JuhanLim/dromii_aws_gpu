from django.db import models
from django.contrib.auth.models import User
from .instance import Instance

class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True)
    scheduled_end = models.DateTimeField(null=True)