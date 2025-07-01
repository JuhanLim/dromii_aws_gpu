from django.urls import path
from . import views

urlpatterns = [
    # 대시보드 - 메인 페이지
    path('', views.dashboard, name='dashboard'),
    
    # 인스턴스 상세 정보
    path('instance/<str:instance_id>/', views.instance_detail, name='instance_detail'),
    
    # 인스턴스 생성
    path('create/', views.create_instance_form, name='create_instance_form'),
    path('create/submit/', views.create_instance, name='create_instance'),
    
    # API 엔드포인트
    path('api/control/', views.control_instance, name='control_instance'),
    path('api/status/<str:instance_id>/', views.check_instance_status, name='check_instance_status'),
    path('api/tags/', views.manage_tags, name='manage_tags'),
]
