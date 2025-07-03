from django.urls import path
from . import views
from . import auth_views
from . import reservation_views

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
    
    # 인증 관련 URL
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    path('register/', auth_views.register_view, name='register'),
    path('profile/', auth_views.profile_view, name='profile'),
    
    # 예약 관련 URL
    path('reservations/', reservation_views.reservation_list, name='reservation_list'),
    path('reservations/create/<str:instance_id>/', reservation_views.create_reservation, name='create_reservation'),
    path('reservations/<int:reservation_id>/', reservation_views.reservation_detail, name='reservation_detail'),
    path('reservations/<int:reservation_id>/cancel/', reservation_views.cancel_reservation, name='cancel_reservation'),
    path('reservations/admin/', reservation_views.admin_reservation_list, name='admin_reservation_list'),
    path('reservations/admin/<int:reservation_id>/update/', reservation_views.admin_reservation_update, name='admin_reservation_update'),
    path('reservations/availability/<str:instance_id>/', reservation_views.instance_availability, name='instance_availability'),
    
    # 예약 관련 API URL
    path('api/reservations/<int:reservation_id>/', reservation_views.reservation_detail_api, name='reservation_detail_api'),
    path('api/reservations/admin/<int:reservation_id>/update/', reservation_views.admin_reservation_update_api, name='admin_reservation_update_api'),
]
