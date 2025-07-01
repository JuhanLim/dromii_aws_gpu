from django.db import models

class Instance(models.Model):
    instance_id = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    instance_type = models.CharField(max_length=20)
    state = models.CharField(max_length=20)