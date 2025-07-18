from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.
class Instance(models.Model):
    """인스턴스 모델"""
    instance_id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=255)
    instance_type = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    public_ip = models.CharField(max_length=100, null=True, blank=True)
    private_ip = models.CharField(max_length=100, null=True, blank=True)
    launch_time = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.instance_id})"

class Reservation(models.Model):
    """예약 모델"""
    STATUS_CHOICES = (
        ('pending', '대기 중'),
        ('approved', '승인됨'),
        ('rejected', '거절됨'),
        ('canceled', '취소됨'),
        ('completed', '완료됨'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    purpose = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}의 {self.instance.name} 예약 ({self.start_time} ~ {self.end_time})"

class Profile(models.Model):
    """사용자 프로필 모델"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='전화번호')
    
    class Meta:
        verbose_name = '프로필'
        verbose_name_plural = '프로필'
    
    def __str__(self):
        return f"{self.user.username}의 프로필"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """사용자 생성 시 프로필 자동 생성"""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """사용자 저장 시 프로필 자동 저장"""
    if hasattr(instance, 'profile'):
        instance.profile.save()
    else:
        Profile.objects.create(user=instance)
