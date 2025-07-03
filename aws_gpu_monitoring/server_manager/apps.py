from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class ServerManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'server_manager'
    
    def ready(self):
        """
        Django 애플리케이션 시작 시 실행되는 메서드
        스케줄러 초기화 및 시작
        """
        # 개발 환경에서 리로드 시 중복 실행 방지
        import sys
        if 'runserver' not in sys.argv:
            return
            
        # 스케줄러 초기화 및 시작
        try:
            from .scheduler import initialize_scheduler
            initialize_scheduler()
            logger.info('예약 스케줄러가 초기화되고 시작되었습니다.')
        except Exception as e:
            logger.error(f'예약 스케줄러 초기화 중 오류 발생: {str(e)}')
