from django.apps import AppConfig
import logging
import os
import sys

logger = logging.getLogger(__name__)

class ServerManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'server_manager'
    
    def ready(self):
        """
        Django 애플리케이션 시작 시 실행되는 메서드
        스케줄러 초기화 및 시작
        """
        # 중복 실행 방지를 위한 환경 변수 확인
        RUN_MAIN = os.environ.get('RUN_MAIN')
        
        # Django runserver는 리로딩을 위해 두 번 실행되므로, 
        # RUN_MAIN이 'true'일 때만 스케줄러 실행 (메인 프로세스에서만)
        if 'runserver' in sys.argv and RUN_MAIN != 'true':
            logger.info('Django 개발 서버 리로더 프로세스에서는 스케줄러를 시작하지 않습니다.')
            return
            
        # 프로덕션 환경에서는 WSGI 애플리케이션이 여러 번 로드될 수 있으므로
        # 환경 변수를 사용하여 한 번만 실행되도록 함
        if os.environ.get('SCHEDULER_RUNNING') == 'true':
            logger.info('스케줄러가 이미 다른 프로세스에서 실행 중입니다.')
            return
            
        # 스케줄러 실행 중 표시
        os.environ['SCHEDULER_RUNNING'] = 'true'
            
        # 스케줄러 초기화 및 시작
        try:
            from .scheduler import initialize_scheduler, scheduler
            
            # 스케줄러가 이미 실행 중인지 확인
            if scheduler.running:
                logger.info("스케줄러가 이미 실행 중입니다.")
            else:
                # 스케줄러 초기화
                initialize_scheduler()
                logger.info('예약 스케줄러가 초기화되고 시작되었습니다.')
                
                # 스케줄러 상태 확인
                if scheduler.running:
                    logger.info("스케줄러가 실행 중입니다.")
                    jobs = scheduler.get_jobs()
                    logger.info(f"등록된 작업 수: {len(jobs)}")
                    for job in jobs:
                        logger.info(f"작업: {job.id}, 다음 실행: {job.next_run_time}")
                else:
                    logger.error("스케줄러가 초기화되었지만 실행 중이 아닙니다.")
        except Exception as e:
            logger.error(f'예약 스케줄러 초기화 중 오류 발생: {str(e)}')
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
