from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Instance, Reservation, User

# Register your models here.
admin.site.register(Instance)
admin.site.register(Reservation)

# 커스텀 User 모델을 위한 Admin 설정
class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'phone_number', 'first_name', 'last_name', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('추가 정보', {'fields': ('phone_number',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('추가 정보', {'fields': ('phone_number',)}),
    )

# User 모델 등록
admin.site.register(User, CustomUserAdmin)
