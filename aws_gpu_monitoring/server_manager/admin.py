from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Instance, Reservation, Profile

# Register your models here.
admin.site.register(Instance)
admin.site.register(Reservation)

# 프로필을 인라인으로 표시하기 위한 설정
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = '프로필'

# 기존 UserAdmin 확장
class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline, )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_phone_number')
    
    def get_phone_number(self, obj):
        if hasattr(obj, 'profile') and obj.profile:
            return obj.profile.phone_number
        return '-'
    
    get_phone_number.short_description = '전화번호'

# 기존 User 모델에 대한 admin 재등록
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
