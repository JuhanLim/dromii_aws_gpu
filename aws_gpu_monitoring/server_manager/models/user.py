from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    """
    사용자 계정 관리를 위한 커스텀 매니저
    """
    def create_user(self, email, username, password=None, **extra_fields):
        """
        일반 사용자 생성
        """
        if not email:
            raise ValueError(_('이메일 주소는 필수입니다.'))
        if not username:
            raise ValueError(_('사용자 이름은 필수입니다.'))
        
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        """
        관리자 사용자 생성
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_admin', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser는 is_staff=True여야 합니다.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser는 is_superuser=True여야 합니다.'))
        
        return self.create_user(email, username, password, **extra_fields)


class User(AbstractUser):
    """
    커스텀 사용자 모델
    """
    email = models.EmailField(_('이메일 주소'), unique=True)
    username = models.CharField(_('사용자 이름'), max_length=50, unique=True)
    first_name = models.CharField(_('이름'), max_length=30, blank=True)
    last_name = models.CharField(_('성'), max_length=30, blank=True)
    is_active = models.BooleanField(_('활성화 상태'), default=True)
    is_staff = models.BooleanField(_('스태프 상태'), default=False)
    is_admin = models.BooleanField(_('관리자 상태'), default=False)
    date_joined = models.DateTimeField(_('가입일'), auto_now_add=True)
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        verbose_name = _('사용자')
        verbose_name_plural = _('사용자')
        db_table = 'server_manager_user'
        
    def __str__(self):
        return self.email
    
    def has_perm(self, perm, obj=None):
        return True
    
    def has_module_perms(self, app_label):
        return True
