from django.db import models
from django.utils.translation import gettext_lazy as _
from .instance import Instance
from .user import User


class Reservation(models.Model):
    """
    인스턴스 사용 예약 모델
    """
    STATUS_CHOICES = (
        ('pending', '대기중'),
        ('approved', '승인됨'),
        ('rejected', '거부됨'),
        ('canceled', '취소됨'),
        ('completed', '완료됨'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservations', verbose_name=_('사용자'))
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name='reservations', verbose_name=_('인스턴스'))
    start_time = models.DateTimeField(_('시작 시간'))
    end_time = models.DateTimeField(_('종료 시간'))
    status = models.CharField(_('상태'), max_length=20, choices=STATUS_CHOICES, default='pending')
    purpose = models.TextField(_('사용 목적'), blank=True, null=True)
    created_at = models.DateTimeField(_('생성일'), auto_now_add=True)
    updated_at = models.DateTimeField(_('수정일'), auto_now=True)
    admin_comment = models.TextField(_('관리자 코멘트'), blank=True, null=True)
    
    class Meta:
        verbose_name = _('예약')
        verbose_name_plural = _('예약')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username}의 {self.instance.name} 예약 ({self.start_time.strftime('%Y-%m-%d %H:%M')} ~ {self.end_time.strftime('%Y-%m-%d %H:%M')})"
    
    def is_active(self):
        """
        현재 활성화된 예약인지 확인
        """
        from django.utils import timezone
        now = timezone.now()
        return self.status == 'approved' and self.start_time <= now <= self.end_time
    
    def duration_hours(self):
        """
        예약 시간 (시간 단위)
        """
        delta = self.end_time - self.start_time
        return delta.total_seconds() / 3600
