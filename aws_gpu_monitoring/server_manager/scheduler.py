from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django.conf import settings
from django.utils import timezone
import logging
import datetime
import sys

from .ec2_service import EC2Service

logger = logging.getLogger(__name__)
ec2_service = EC2Service()

# 스케줄러 인스턴스 생성
scheduler = BackgroundScheduler()
scheduler.add_jobstore(DjangoJobStore(), "default")

# 스케줄러 이벤트 리스너 추가
def job_executed_event(event):
    """
    작업 실행 이벤트 핸들러
    """
    job_id = event.job_id
    logger.info(f"작업 실행됨: {job_id}, 실행 시간: {timezone.localtime().strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    
def job_error_event(event):
    """
    작업 오류 이벤트 핸들러
    """
    job_id = event.job_id
    exception = event.exception
    traceback = event.traceback
    logger.error(f"작업 실행 중 오류 발생: {job_id}")
    logger.error(f"예외: {exception}")
    logger.error(f"트레이스백: {traceback}")

# 이벤트 리스너 등록
scheduler.add_listener(job_executed_event, 'executed')
scheduler.add_listener(job_error_event, 'error')

def start_instance_job(instance_id, reservation_id):
    """
    예약된 시간에 인스턴스를 시작하는 작업
    """
    try:
        logger.info(f"예약 {reservation_id}에 따라 인스턴스 {instance_id} 시작 작업 실행")
        response = ec2_service.start_instance(instance_id)
        if response['success']:
            logger.info(f"인스턴스 {instance_id} 시작 성공: {response['message']}")
        else:
            logger.error(f"인스턴스 {instance_id} 시작 실패: {response['message']}")
    except Exception as e:
        logger.error(f"인스턴스 {instance_id} 시작 중 오류 발생: {str(e)}")

def stop_instance_job(instance_id, reservation_id):
    """
    예약된 시간에 인스턴스를 중지하는 작업
    """
    try:
        # 현재 시간 로깅 (서버 시간과 UTC 시간 모두 기록)
        now_local = timezone.localtime()
        now_utc = timezone.now()
        logger.info(f"예약 {reservation_id}에 따라 인스턴스 {instance_id} 중지 작업 실행")
        logger.info(f"현재 서버 시간(한국): {now_local.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        logger.info(f"현재 UTC 시간: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        
        # 예약 정보 조회 및 로깅
        from .models import Reservation
        try:
            reservation = Reservation.objects.get(id=reservation_id)
            logger.info(f"예약 정보 - 시작: {reservation.start_time}, 종료: {reservation.end_time}")
        except Reservation.DoesNotExist:
            logger.warning(f"예약 ID {reservation_id}에 해당하는 예약 정보를 찾을 수 없습니다.")
        
        # 인스턴스 상태 확인
        status_response = ec2_service.get_instance_status(instance_id)
        if status_response['success']:
            current_state = status_response['data']['state']
            logger.info(f"중지 작업 전 인스턴스 {instance_id}의 현재 상태: {current_state}")
            
            # 이미 중지된 상태인지 확인
            if current_state in ['stopped', 'stopping']:
                logger.info(f"인스턴스 {instance_id}는 이미 {current_state} 상태입니다. 중지 작업을 건너뜁니다.")
                return
        else:
            logger.warning(f"인스턴스 상태 확인 실패: {status_response['message']}")
        
        # 인스턴스 중지 요청
        logger.info(f"인스턴스 {instance_id} 중지 요청 시작")
        response = ec2_service.stop_instance(instance_id)
        logger.info(f"인스턴스 {instance_id} 중지 요청 응답: {response}")
        
        if response['success']:
            logger.info(f"인스턴스 {instance_id} 중지 성공: {response['message']}")
        else:
            logger.error(f"인스턴스 {instance_id} 중지 실패: {response['message']}")
            
        # 중지 요청 후 상태 다시 확인
        try:
            status_after = ec2_service.get_instance_status(instance_id)
            if status_after['success']:
                logger.info(f"중지 요청 후 인스턴스 {instance_id}의 상태: {status_after['data']['state']}")
            else:
                logger.warning(f"중지 요청 후 인스턴스 상태 확인 실패: {status_after['message']}")
        except Exception as e:
            logger.error(f"중지 요청 후 상태 확인 중 오류: {str(e)}")
            
    except Exception as e:
        logger.error(f"인스턴스 {instance_id} 중지 중 오류 발생: {str(e)}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")

def schedule_reservation_jobs(reservation):
    """
    예약에 대한 시작 및 종료 작업 스케줄링
    """
    if reservation.status != 'approved':
        # 승인된 예약만 스케줄링
        logger.info(f"예약 ID {reservation.id}는 승인되지 않아 스케줄링하지 않습니다. 현재 상태: {reservation.status}")
        return
    
    instance_id = reservation.instance.instance_id
    reservation_id = reservation.id
    
    # 현재 시간 (로컬 및 UTC)
    now = timezone.now()
    now_local = timezone.localtime(now)
    
    # 시간 정보 로깅
    logger.info(f"예약 ID {reservation_id} 스케줄링 시작")
    logger.info(f"현재 서버 시간(한국): {now_local.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    logger.info(f"현재 UTC 시간: {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    logger.info(f"예약 시작 시간: {reservation.start_time.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    logger.info(f"예약 종료 시간: {reservation.end_time.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    
    # 시작 시간이 현재보다 미래인 경우에만 시작 작업 스케줄링
    if reservation.start_time > now:
        start_job_id = f"start_instance_{reservation_id}"
        scheduler.add_job(
            start_instance_job,
            trigger='date',
            run_date=reservation.start_time,
            id=start_job_id,
            replace_existing=True,
            args=[instance_id, reservation_id],
            name=f"인스턴스 {instance_id} 시작 (예약 ID: {reservation_id})"
        )
        logger.info(f"인스턴스 {instance_id} 시작 작업이 {reservation.start_time}에 예약되었습니다.")
    else:
        logger.info(f"인스턴스 {instance_id} 시작 시간이 현재보다 과거이므로 시작 작업을 스케줄링하지 않습니다.")
    
    # 종료 시간이 현재보다 미래인 경우에만 종료 작업 스케줄링
    if reservation.end_time > now:
        stop_job_id = f"stop_instance_{reservation_id}"
        scheduler.add_job(
            stop_instance_job,
            trigger='date',
            run_date=reservation.end_time,
            id=stop_job_id,
            replace_existing=True,
            args=[instance_id, reservation_id],
            name=f"인스턴스 {instance_id} 중지 (예약 ID: {reservation_id})"
        )
        logger.info(f"인스턴스 {instance_id} 중지 작업이 {reservation.end_time}에 예약되었습니다.")
    else:
        logger.info(f"인스턴스 {instance_id} 종료 시간이 현재보다 과거이므로 중지 작업을 스케줄링하지 않습니다.")

def cancel_reservation_jobs(reservation):
    """
    예약에 대한 스케줄링된 작업 취소
    """
    reservation_id = reservation.id
    
    # 시작 작업 취소
    start_job_id = f"start_instance_{reservation_id}"
    try:
        scheduler.remove_job(start_job_id)
        logger.info(f"예약 {reservation_id}에 대한 시작 작업이 취소되었습니다.")
    except Exception as e:
        logger.debug(f"예약 {reservation_id}에 대한 시작 작업 취소 실패: {str(e)}")
    
    # 종료 작업 취소
    stop_job_id = f"stop_instance_{reservation_id}"
    try:
        scheduler.remove_job(stop_job_id)
        logger.info(f"예약 {reservation_id}에 대한 종료 작업이 취소되었습니다.")
    except Exception as e:
        logger.debug(f"예약 {reservation_id}에 대한 종료 작업 취소 실패: {str(e)}")

def initialize_scheduler():
    """
    스케줄러 초기화 및 기존 예약 로드
    """
    from .models import Reservation
    
    # 현재 시간 로깅
    now = timezone.now()
    now_local = timezone.localtime(now)
    logger.info(f"스케줄러 초기화 시작 - 현재 서버 시간(한국): {now_local.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    logger.info(f"현재 UTC 시간: {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
    
    # 스케줄러 상태 확인
    if scheduler.running:
        logger.info("스케줄러가 이미 실행 중입니다. 기존 작업을 확인합니다.")
        jobs = scheduler.get_jobs()
        logger.info(f"현재 스케줄러에 등록된 작업 수: {len(jobs)}")
        for job in jobs:
            logger.info(f"작업 ID: {job.id}, 다음 실행 시간: {job.next_run_time}")
    
    # 승인된 예약 중 종료 시간이 현재보다 미래인 것만 로드
    active_reservations = Reservation.objects.filter(
        status='approved',
        end_time__gt=now
    )
    
    logger.info(f"활성 예약 조회 결과: {active_reservations.count()}개 발견")
    
    for reservation in active_reservations:
        logger.info(f"예약 ID {reservation.id} 스케줄링 시작 (인스턴스: {reservation.instance.instance_id})")
        schedule_reservation_jobs(reservation)
    
    logger.info(f"{active_reservations.count()}개의 활성 예약이 스케줄러에 로드되었습니다.")
    
    # 스케줄러 시작
    if not scheduler.running:
        try:
            scheduler.start()
            logger.info("스케줄러가 성공적으로 시작되었습니다.")
        except Exception as e:
            logger.error(f"스케줄러 시작 중 오류 발생: {str(e)}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
    else:
        logger.info("스케줄러가 이미 실행 중입니다. 새로 시작하지 않습니다.")
    
    # 등록된 작업 확인
    jobs_after = scheduler.get_jobs()
    logger.info(f"초기화 후 스케줄러에 등록된 작업 수: {len(jobs_after)}")
    for job in jobs_after:
        logger.info(f"작업 ID: {job.id}, 다음 실행 시간: {job.next_run_time}")
