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
    
    def increment_restart_attempts(self):
        """재시작 시도 횟수를 증가시키고 마지막 시도 시간을 업데이트합니다."""
        self.restart_attempts += 1
        self.last_restart_attempt = timezone.now()
        self.save(update_fields=['restart_attempts', 'last_restart_attempt'])
    
    def reset_restart_attempts(self):
        """재시작 시도 횟수를 초기화합니다."""
        self.restart_attempts = 0
        self.save(update_fields=['restart_attempts'])
    
    def toggle_auto_restart(self):
        """자동 재시작 상태를 토글합니다."""
        self.auto_restart_enabled = not self.auto_restart_enabled
        self.save(update_fields=['auto_restart_enabled'])
        return self.auto_restart_enabled