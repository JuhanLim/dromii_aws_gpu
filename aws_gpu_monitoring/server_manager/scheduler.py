from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from django_apscheduler.jobstores import DjangoJobStore
from django.conf import settings
from django.utils import timezone
import logging
import datetime
import sys
import pytz

from .ec2_service import EC2Service

logger = logging.getLogger(__name__)
ec2_service = EC2Service()

# 스케줄러 인스턴스 생성
scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Seoul'))
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

def job_missed_event(event):
    """
    작업 누락 이벤트 핸들러
    """
    job_id = event.job_id
    scheduled_run_time = event.scheduled_run_time
    logger.warning(f"작업 누락됨: {job_id}, 예정된 실행 시간: {scheduled_run_time}")

# 이벤트 리스너 등록
scheduler.add_listener(job_executed_event, EVENT_JOB_EXECUTED)
scheduler.add_listener(job_error_event, EVENT_JOB_ERROR)
scheduler.add_listener(job_missed_event, EVENT_JOB_MISSED)

def start_instance_job(instance_id, reservation_id):
    """
    예약된 시간에 인스턴스를 시작하는 작업
    """
    # 작업 시작 로그 - 눈에 띄게 표시
    logger.info(f"======================================================")
    logger.info(f"===== 인스턴스 시작 작업 실행 시작 - {timezone.localtime()} =====")
    logger.info(f"======================================================")
    
    try:
        # 현재 시간 로깅 (서버 시간과 UTC 시간 모두 기록)
        now_local = timezone.localtime()
        now_utc = timezone.now()
        logger.info(f"예약 {reservation_id}에 따라 인스턴스 {instance_id} 시작 작업 실행")
        logger.info(f"현재 서버 시간(한국): {now_local.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        logger.info(f"현재 UTC 시간: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z%z')}")
        
        # 예약 정보 조회 및 로깅
        from .models import Reservation
        try:
            reservation = Reservation.objects.get(id=reservation_id)
            logger.info(f"예약 정보 - 시작: {reservation.start_time}, 종료: {reservation.end_time}, 상태: {reservation.status}")
        except Reservation.DoesNotExist:
            logger.warning(f"예약 ID {reservation_id}에 해당하는 예약 정보를 찾을 수 없습니다.")
        
        # 인스턴스 상태 확인
        logger.info(f"인스턴스 {instance_id} 상태 확인 중...")
        status_response = ec2_service.get_instance_status(instance_id)
        if status_response['success']:
            current_state = status_response['data']['state']
            logger.info(f"시작 작업 전 인스턴스 {instance_id}의 현재 상태: {current_state}")
            
            # 이미 실행 중이거나 시작 중인 상태인지 확인
            if current_state in ['running', 'pending']:
                logger.info(f"인스턴스 {instance_id}는 이미 {current_state} 상태입니다. 시작 작업을 건너뜁니다.")
                return
            # 중지 중인 상태인지 확인
            elif current_state == 'stopping':
                logger.warning(f"인스턴스 {instance_id}는 현재 {current_state} 상태입니다. 완전히 중지될 때까지 기다려야 합니다.")
                return
        else:
            logger.warning(f"인스턴스 상태 확인 실패: {status_response['message']}")
            # 상태 확인 실패해도 시작 시도
            logger.info(f"상태 확인 실패했지만 시작 작업 계속 진행합니다.")
        
        # 인스턴스 시작 요청 - 여러 번 시도
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            logger.info(f"인스턴스 {instance_id} 시작 요청 시작 (시도 {attempt}/{max_attempts})...")
            response = ec2_service.start_instance(instance_id)
            logger.info(f"인스턴스 {instance_id} 시작 요청 응답 (시도 {attempt}): {response}")
            
            if response['success']:
                logger.info(f"인스턴스 {instance_id} 시작 요청이 성공적으로 처리되었습니다.")
                break
            else:
                logger.error(f"인스턴스 {instance_id} 시작 요청 실패 (시도 {attempt}): {response['message']}")
                if attempt < max_attempts:
                    import time
                    logger.info(f"3초 후 다시 시도합니다...")
                    time.sleep(3)
        
        # 시작 요청 후 상태 확인
        try:
            logger.info(f"시작 요청 후 인스턴스 상태 확인 중...")
            status_after = ec2_service.get_instance_status(instance_id)
            if status_after['success']:
                after_state = status_after['data']['state']
                logger.info(f"시작 요청 후 인스턴스 {instance_id}의 상태: {after_state}")
            else:
                logger.warning(f"시작 요청 후 상태 확인 실패: {status_after['message']}")
        except Exception as status_error:
            logger.error(f"시작 요청 후 상태 확인 중 오류: {str(status_error)}")
            import traceback
            logger.error(f"상태 확인 오류 상세: {traceback.format_exc()}")
        
        logger.info(f"======================================================")
        logger.info(f"===== 인스턴스 시작 작업 실행 완료 - {timezone.localtime()} =====")
        logger.info(f"======================================================")
            
    except Exception as e:
        logger.error(f"인스턴스 {instance_id} 시작 중 오류 발생: {str(e)}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")

def stop_instance_job(instance_id, reservation_id):
    """
    예약된 시간에 인스턴스를 중지하는 작업
    """
    # 작업 시작 로그 - 눈에 띄게 표시
    logger.info(f"======================================================")
    logger.info(f"===== 인스턴스 중지 작업 실행 시작 - {timezone.localtime()} =====")
    logger.info(f"======================================================")
    
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
            logger.info(f"예약 정보 - 시작: {reservation.start_time}, 종료: {reservation.end_time}, 상태: {reservation.status}")
        except Reservation.DoesNotExist:
            logger.warning(f"예약 ID {reservation_id}에 해당하는 예약 정보를 찾을 수 없습니다.")
        
        # 인스턴스 상태 확인
        logger.info(f"인스턴스 {instance_id} 상태 확인 중...")
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
            # 상태 확인 실패해도 중지 시도
            logger.info(f"상태 확인 실패했지만 중지 작업 계속 진행합니다.")
        
        # 인스턴스 중지 요청 - 여러 번 시도
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            logger.info(f"인스턴스 {instance_id} 중지 요청 시작 (시도 {attempt}/{max_attempts})...")
            response = ec2_service.stop_instance(instance_id)
            logger.info(f"인스턴스 {instance_id} 중지 요청 응답 (시도 {attempt}): {response}")
            
            if response['success']:
                logger.info(f"인스턴스 {instance_id} 중지 요청이 성공적으로 처리되었습니다.")
                break
            else:
                logger.error(f"인스턴스 {instance_id} 중지 요청 실패 (시도 {attempt}): {response['message']}")
                if attempt < max_attempts:
                    import time
                    logger.info(f"3초 후 다시 시도합니다...")
                    time.sleep(3)
        
        # 중지 요청 후 상태 확인
        try:
            logger.info(f"중지 요청 후 인스턴스 상태 확인 중...")
            status_after = ec2_service.get_instance_status(instance_id)
            if status_after['success']:
                after_state = status_after['data']['state']
                logger.info(f"중지 요청 후 인스턴스 {instance_id}의 상태: {after_state}")
            else:
                logger.warning(f"중지 요청 후 상태 확인 실패: {status_after['message']}")
        except Exception as status_error:
            logger.error(f"중지 요청 후 상태 확인 중 오류: {str(status_error)}")
            import traceback
            logger.error(f"상태 확인 오류 상세: {traceback.format_exc()}")
        
        # 예약 상태 업데이트
        try:
            if 'reservation' in locals() and reservation:
                reservation.status = 'completed'
                reservation.save()
                logger.info(f"예약 ID {reservation_id} 상태를 'completed'로 업데이트했습니다.")
        except Exception as update_error:
            logger.error(f"예약 상태 업데이트 중 오류: {str(update_error)}")
            
        logger.info(f"======================================================")
        logger.info(f"===== 인스턴스 중지 작업 실행 완료 - {timezone.localtime()} =====")
        logger.info(f"======================================================")
            
    except Exception as e:
        logger.error(f"인스턴스 {instance_id} 중지 중 오류 발생: {str(e)}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")
        logger.error(f"======================================================")
        logger.error(f"===== 인스턴스 중지 작업 실행 실패 - {timezone.localtime()} =====")
        logger.error(f"======================================================")

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
    
    # 연장/겹침/인접(끝=시작) 예약 처리: 기존 종료 작업 취소
    try:
        from .models import Reservation as _ResvModel
        overlapping_approved = _ResvModel.objects.filter(
            instance=reservation.instance,
            status='approved'
        ).exclude(id=reservation_id).filter(
            # 기존 예약이 새 예약 시작과 겹치거나(또는 인접) 있고,
            end_time__gte=reservation.start_time,
            # 새 예약 종료 이전(또는 같음)에 끝나는 예약만 대상으로 함
            end_time__lte=reservation.end_time
        )
        for prev in overlapping_approved:
            prev_stop_job_id = f"stop_instance_{prev.id}"
            try:
                job = scheduler.get_job(prev_stop_job_id)
                if job:
                    scheduler.remove_job(prev_stop_job_id)
                    logger.info(f"연장 처리: 기존 예약(ID={prev.id})의 종료 작업을 취소했습니다. (job_id={prev_stop_job_id})")
            except Exception as _e:
                logger.error(f"연장 처리: 기존 예약(ID={prev.id}) 종료 작업 취소 중 오류: {_e}")
    except Exception as merge_e:
        logger.error(f"연장/겹침 예약 처리 중 오류: {merge_e}")
    
    # 시작 시간이 현재보다 미래인 경우 스케줄링, 과거인 경우 즉시 실행
    start_job_id = f"start_instance_{reservation_id}"
    start_job_scheduled = False  # 스케줄러에 작업이 등록되었는지 추적
    
    try:
        if reservation.start_time > now:
            # 미래 시간인 경우 예약
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
            start_job_scheduled = True
        else:
            # 과거 시간인 경우 즉시 실행
            logger.info(f"예약 시작 시간이 현재보다 과거입니다. 인스턴스 {instance_id} 시작 작업을 즉시 실행합니다.")
            start_instance_job(instance_id, reservation_id)
            logger.info(f"인스턴스 {instance_id} 시작 작업이 즉시 실행되었습니다. 스케줄러 등록은 건너뜁니다.")
            # 스케줄러에 작업 추가는 하지 않음
        
        # 작업이 제대로 등록되었는지 확인 (스케줄러에 등록된 경우만)
        if start_job_scheduled:
            job = scheduler.get_job(start_job_id)
            if job:
                next_run_utc = getattr(job, 'next_run_time', None)
                try:
                    next_run_kst = timezone.localtime(next_run_utc) if next_run_utc else None
                except Exception:
                    next_run_kst = None
                logger.info(f"시작 작업 확인: ID={job.id}, 다음 실행 시간(UTC)={next_run_utc}, (KST)={next_run_kst}")
            else:
                logger.error(f"시작 작업이 등록되지 않았습니다: {start_job_id}")
    except Exception as e:
        logger.error(f"시작 작업 스케줄링 중 오류: {str(e)}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")
    # else:
    #     logger.info(f"인스턴스 {instance_id} 시작 시간이 현재보다 과거이므로 시작 작업을 스케줄링하지 않습니다.")
    
    # 종료 시간이 현재보다 미래인 경우에만 종료 작업 스케줄링
    if reservation.end_time > now:
        stop_job_id = f"stop_instance_{reservation_id}"
        test_stop_job_id = None  # 변수 미리 초기화
        
        try:
            # 디버깅 모드인 경우에만 테스트 작업 추가 (개발 환경에서만)
            if 'runserver' in sys.argv:
                # 현재 시간으로부터 10초 후에 즉시 실행하는 테스트 작업 추가 (디버깅용)
                test_stop_job_id = f"test_stop_instance_{reservation_id}"
                test_run_date = now + datetime.timedelta(seconds=10)
                try:
                    scheduler.add_job(
                        stop_instance_job,
                        trigger='date',
                        run_date=test_run_date,
                        id=test_stop_job_id,
                        replace_existing=True,
                        args=[instance_id, reservation_id],
                        name=f"인스턴스 {instance_id} 테스트 중지 (예약 ID: {reservation_id})"
                    )
                    logger.info(f"인스턴스 {instance_id} 테스트 중지 작업이 {test_run_date}에 예약되었습니다.")
                except Exception as test_error:
                    logger.error(f"테스트 중지 작업 스케줄링 중 오류: {str(test_error)}")
            
            # 실제 종료 작업 예약
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
            
            # 작업이 제대로 등록되었는지 확인
            job = scheduler.get_job(stop_job_id)
            if job:
                next_run = getattr(job, 'next_run_time', None)
                logger.info(f"중지 작업 확인: ID={job.id}, 다음 실행 시간={next_run}")
            else:
                logger.error(f"중지 작업이 등록되지 않았습니다: {stop_job_id}")
                
            # 테스트 작업 확인 (테스트 작업이 생성된 경우에만)
            if test_stop_job_id:
                test_job = scheduler.get_job(test_stop_job_id)
                if test_job:
                    test_next = getattr(test_job, 'next_run_time', None)
                    logger.info(f"테스트 중지 작업 확인: ID={test_job.id}, 다음 실행 시간={test_next}")
                else:
                    logger.error(f"테스트 중지 작업이 등록되지 않았습니다: {test_stop_job_id}")
        except Exception as e:
            logger.error(f"중지 작업 스케줄링 중 오류: {str(e)}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
    else:
        logger.info(f"인스턴스 {instance_id} 종료 시간이 현재보다 과거이므로 중지 작업을 스케줄링하지 않습니다.")

def cancel_reservation_jobs(reservation):
    """
    예약에 대한 스케줄링된 작업 취소
    
    Args:
        reservation: 취소할 예약 객체
        
    Returns:
        dict: 작업 취소 결과 {'start_job_canceled': bool, 'stop_job_canceled': bool}
    """
    reservation_id = reservation.id
    instance_id = reservation.instance.instance_id if reservation.instance else "알 수 없음"
    result = {'start_job_canceled': False, 'stop_job_canceled': False}
    
    logger.info(f"예약 ID {reservation_id}, 인스턴스 ID {instance_id}에 대한 스케줄링된 작업 취소 시작")
    
    # 시작 작업 취소
    start_job_id = f"start_instance_{reservation_id}"
    try:
        # 작업이 존재하는지 확인
        job = scheduler.get_job(start_job_id)
        if job:
            next_run_time = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else "None"
            logger.info(f"예약 {reservation_id}의 시작 작업 발견. 다음 실행 시간: {next_run_time}")
            
            scheduler.remove_job(start_job_id)
            logger.info(f"예약 {reservation_id}에 대한 시작 작업이 성공적으로 취소되었습니다.")
            result['start_job_canceled'] = True
        else:
            logger.info(f"예약 {reservation_id}에 대한 시작 작업이 스케줄러에 존재하지 않습니다.")
    except Exception as e:
        logger.error(f"예약 {reservation_id}에 대한 시작 작업 취소 실패: {str(e)}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")
    
    # 종료 작업 취소
    stop_job_id = f"stop_instance_{reservation_id}"
    try:
        # 작업이 존재하는지 확인
        job = scheduler.get_job(stop_job_id)
        if job:
            next_run_time = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else "None"
            logger.info(f"예약 {reservation_id}의 종료 작업 발견. 다음 실행 시간: {next_run_time}")
            
            scheduler.remove_job(stop_job_id)
            logger.info(f"예약 {reservation_id}에 대한 종료 작업이 성공적으로 취소되었습니다.")
            result['stop_job_canceled'] = True
        else:
            logger.info(f"예약 {reservation_id}에 대한 종료 작업이 스케줄러에 존재하지 않습니다.")
    except Exception as e:
        logger.error(f"예약 {reservation_id}에 대한 종료 작업 취소 실패: {str(e)}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")
    
    # 테스트 종료 작업 취소 (개발 환경 runserver에서 생성된 경우)
    test_stop_job_id = f"test_stop_instance_{reservation_id}"
    try:
        test_job = scheduler.get_job(test_stop_job_id)
        if test_job:
            next_run_utc = getattr(test_job, 'next_run_time', None)
            try:
                next_run_kst = timezone.localtime(next_run_utc) if next_run_utc else None
            except Exception:
                next_run_kst = None
            logger.info(f"예약 {reservation_id}의 테스트 종료 작업 발견. 다음 실행 시간(UTC): {next_run_utc}, (KST): {next_run_kst}")
            scheduler.remove_job(test_stop_job_id)
            logger.info(f"예약 {reservation_id}에 대한 테스트 종료 작업이 성공적으로 취소되었습니다.")
    except Exception as e:
        logger.error(f"예약 {reservation_id}에 대한 테스트 종료 작업 취소 실패: {str(e)}")
    
    logger.info(f"예약 ID {reservation_id} 작업 취소 결과: {result}")
    return result

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
        try:
            jobs = scheduler.get_jobs()
            logger.info(f"현재 스케줄러에 등록된 작업 수: {len(jobs)}")
            for job in jobs:
                if hasattr(job, 'next_run_time'):
                    logger.info(f"작업 ID: {job.id}, 다음 실행 시간: {job.next_run_time}")
                else:
                    logger.info(f"작업 ID: {job.id}, 다음 실행 시간: 알 수 없음")
        except Exception as e:
            logger.error(f"작업 목록 확인 중 오류: {str(e)}")
    
    # 승인된 예약 중 종료 시간이 현재보다 미래인 것만 로드
    try:
        active_reservations = Reservation.objects.filter(
            status='approved',
            end_time__gt=now
        )
        
        logger.info(f"활성 예약 조회 결과: {active_reservations.count()}개 발견")
        
        for reservation in active_reservations:
            logger.info(f"예약 ID {reservation.id} 스케줄링 시작 (인스턴스: {reservation.instance.instance_id})")
            schedule_reservation_jobs(reservation)
        
        logger.info(f"{active_reservations.count()}개의 활성 예약이 스케줄러에 로드되었습니다.")
    except Exception as e:
        logger.error(f"활성 예약 로드 중 오류: {str(e)}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")
    
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
    try:
        jobs_after = scheduler.get_jobs()
        logger.info(f"초기화 후 스케줄러에 등록된 작업 수: {len(jobs_after)}")
        for job in jobs_after:
            next_run_utc = getattr(job, 'next_run_time', None)
            try:
                next_run_kst = timezone.localtime(next_run_utc) if next_run_utc else None
            except Exception:
                next_run_kst = None
            logger.info(f"작업 ID: {job.id}, 다음 실행 시간(UTC): {next_run_utc}, (KST): {next_run_kst}")
    except Exception as e:
        logger.error(f"작업 목록 확인 중 오류: {str(e)}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")
