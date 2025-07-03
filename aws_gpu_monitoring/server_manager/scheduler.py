from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django.conf import settings
from django.utils import timezone
import logging
import datetime

from .ec2_service import EC2Service

logger = logging.getLogger(__name__)
ec2_service = EC2Service()

# 스케줄러 인스턴스 생성
scheduler = BackgroundScheduler()
scheduler.add_jobstore(DjangoJobStore(), "default")

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
        logger.info(f"예약 {reservation_id}에 따라 인스턴스 {instance_id} 중지 작업 실행")
        response = ec2_service.stop_instance(instance_id)
        if response['success']:
            logger.info(f"인스턴스 {instance_id} 중지 성공: {response['message']}")
        else:
            logger.error(f"인스턴스 {instance_id} 중지 실패: {response['message']}")
    except Exception as e:
        logger.error(f"인스턴스 {instance_id} 중지 중 오류 발생: {str(e)}")

def schedule_reservation_jobs(reservation):
    """
    예약에 대한 시작 및 종료 작업 스케줄링
    """
    if reservation.status != 'approved':
        # 승인된 예약만 스케줄링
        return
    
    instance_id = reservation.instance.instance_id
    reservation_id = reservation.id
    
    # 현재 시간
    now = timezone.now()
    
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
    
    # 승인된 예약 중 종료 시간이 현재보다 미래인 것만 로드
    now = timezone.now()
    active_reservations = Reservation.objects.filter(
        status='approved',
        end_time__gt=now
    )
    
    for reservation in active_reservations:
        schedule_reservation_jobs(reservation)
    
    logger.info(f"{active_reservations.count()}개의 활성 예약이 스케줄러에 로드되었습니다.")
    
    # 스케줄러 시작
    if not scheduler.running:
        scheduler.start()
        logger.info("스케줄러가 시작되었습니다.")
