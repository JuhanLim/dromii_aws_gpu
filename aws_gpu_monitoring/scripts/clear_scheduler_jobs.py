"""
스케줄러에 남아있는 작업을 제거하는 스크립트
"""
import os
import sys
import django
import logging

# Django 설정 로드
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aws_gpu_monitoring.settings')
django.setup()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 스케줄러 가져오기
from server_manager.scheduler import scheduler

def clear_all_jobs():
    """스케줄러에 등록된 모든 작업을 제거합니다."""
    try:
        # 모든 작업 목록 가져오기
        jobs = scheduler.get_jobs()
        logger.info(f"현재 스케줄러에 등록된 작업 수: {len(jobs)}")
        
        # 각 작업 정보 출력 및 제거
        for job in jobs:
            job_id = job.id
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S%z') if job.next_run_time else "None"
            logger.info(f"작업 ID: {job_id}, 다음 실행 시간: {next_run}")
            
            # 작업 제거
            scheduler.remove_job(job_id)
            logger.info(f"작업 '{job_id}'이(가) 성공적으로 제거되었습니다.")
        
        logger.info("모든 작업이 성공적으로 제거되었습니다.")
        return True
    except Exception as e:
        logger.error(f"작업 제거 중 오류 발생: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def clear_specific_jobs(job_ids):
    """특정 작업 ID 목록에 해당하는 작업을 제거합니다."""
    try:
        for job_id in job_ids:
            job = scheduler.get_job(job_id)
            if job:
                next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S%z') if job.next_run_time else "None"
                logger.info(f"작업 ID: {job_id}, 다음 실행 시간: {next_run}")
                
                # 작업 제거
                scheduler.remove_job(job_id)
                logger.info(f"작업 '{job_id}'이(가) 성공적으로 제거되었습니다.")
            else:
                logger.warning(f"작업 '{job_id}'을(를) 찾을 수 없습니다.")
        
        return True
    except Exception as e:
        logger.error(f"작업 제거 중 오류 발생: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='스케줄러 작업 제거 도구')
    parser.add_argument('--all', action='store_true', help='모든 작업 제거')
    parser.add_argument('--jobs', nargs='+', help='제거할 특정 작업 ID 목록')
    
    args = parser.parse_args()
    
    if args.all:
        clear_all_jobs()
    elif args.jobs:
        clear_specific_jobs(args.jobs)
    else:
        # 기본적으로 로그에서 발견된 작업 제거
        default_jobs = ['start_instance_23', 'stop_instance_23']
        logger.info(f"기본 작업 제거 모드: {', '.join(default_jobs)}")
        clear_specific_jobs(default_jobs)