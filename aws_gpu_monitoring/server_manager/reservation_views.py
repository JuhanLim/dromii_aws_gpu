from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q
import json
import datetime
import pytz
from django.views.decorators.csrf import csrf_exempt

from .models import Instance, Reservation
from .forms import ReservationForm, ReservationAdminForm
from .scheduler import schedule_reservation_jobs, cancel_reservation_jobs
import logging
logger = logging.getLogger('server_manager')

@login_required
def reservation_list(request):
    """
    사용자의 예약 목록 조회
    """
    reservations = Reservation.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'server_manager/reservation/list.html', {'reservations': reservations})


@login_required
def create_reservation(request, instance_id):
    """
    새 예약 생성
    """
    instance = get_object_or_404(Instance, instance_id=instance_id)
    
    if request.method == 'POST':
        form = ReservationForm(request.POST)
        if form.is_valid():
            # 동일 시간대에 예약이 있는지 확인
            start_time = form.cleaned_data['start_time']
            end_time = form.cleaned_data['end_time']
            
            overlapping_reservations = Reservation.objects.filter(
                instance=instance,
                status='approved',
                start_time__lt=end_time,
                end_time__gt=start_time
            )
            
            if overlapping_reservations.exists():
                messages.error(request, _('해당 시간대에 이미 예약이 존재합니다.'))
            else:
                reservation = form.save(commit=False)
                reservation.user = request.user
                reservation.instance = instance
                reservation.save()
                
                messages.success(request, _('예약 신청이 완료되었습니다. 관리자 승인 후 사용 가능합니다.'))
                return redirect('reservation_list')
    else:
        form = ReservationForm()
    
    return render(request, 'server_manager/reservation/create.html', {
        'form': form,
        'instance': instance
    })


@login_required
def cancel_reservation(request, reservation_id):
    """
    예약 취소
    """
    # 관리자인 경우 모든 예약 취소 가능, 일반 사용자는 자신의 예약만 취소 가능
    if request.user.is_admin:
        reservation = get_object_or_404(Reservation, id=reservation_id)
    else:
        reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
    
    # 예약 상태 변경 및 저장
    previous_status = reservation.status
    reservation.status = 'canceled'
    reservation.save()
    
    # 승인된 예약인 경우에만 스케줄링된 작업 취소
    if previous_status == 'approved':
        try:
            logger.info(f"예약 ID {reservation_id} 취소로 인한 스케줄링된 작업 취소 시작")
            cancel_result = cancel_reservation_jobs(reservation)
            logger.info(f"예약 ID {reservation_id} 취소로 인한 스케줄링된 작업 취소 완료: {cancel_result}")
        except Exception as e:
            logger.error(f"예약 ID {reservation_id} 취소 중 오류 발생: {str(e)}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
    
    messages.success(request, _('예약이 취소되었습니다.'))
    
    # 관리자가 취소한 경우 관리자 페이지로, 일반 사용자가 취소한 경우 예약 목록으로 리다이렉트
    if request.user.is_admin and 'admin' in request.META.get('HTTP_REFERER', ''):
        return redirect('admin_reservation_list')
    else:
        return redirect('reservation_list')


@login_required
def reservation_detail(request, reservation_id):
    """
    예약 상세 정보
    """
    reservation = get_object_or_404(Reservation, id=reservation_id)
    
    # 본인 예약이거나 관리자만 조회 가능
    if reservation.user != request.user and not request.user.is_admin:
        messages.error(request, _('해당 예약에 접근할 권한이 없습니다.'))
        return redirect('reservation_list')
    
    return render(request, 'server_manager/reservation/detail.html', {'reservation': reservation})


@login_required
def admin_reservation_list(request):
    """
    관리자용 전체 예약 목록
    """
    if not request.user.is_admin:
        messages.error(request, _('관리자만 접근할 수 있습니다.'))
        return redirect('dashboard')
    
    status_filter = request.GET.get('status', '')
    
    reservations = Reservation.objects.all().order_by('-created_at')
    if status_filter:
        reservations = reservations.filter(status=status_filter)
    
    return render(request, 'server_manager/reservation/admin_list.html', {
        'reservations': reservations,
        'status_filter': status_filter
    })


@login_required
def admin_reservation_update(request, reservation_id):
    """
    관리자용 예약 상태 업데이트
    """
    if not request.user.is_admin:
        messages.error(request, _('관리자만 접근할 수 있습니다.'))
        return redirect('dashboard')
    
    reservation = get_object_or_404(Reservation, id=reservation_id)
    logger.info(f"관리자 {request.user.username}가 예약 ID {reservation_id} 상태 업데이트 시작")
    
    if request.method == 'POST':
        form = ReservationAdminForm(request.POST, instance=reservation)
        if form.is_valid():
            old_status = reservation.status
            updated_reservation = form.save()
            
            logger.info(f"예약 ID {reservation_id} 상태 변경: {old_status} -> {updated_reservation.status}")
            
            # 상태가 승인됨으로 변경된 경우 스케줄러에 작업 추가
            if old_status != 'approved' and updated_reservation.status == 'approved':
                try:
                    logger.info(f"예약 ID {reservation_id} 승인으로 인한 스케줄링 작업 추가 시작")
                    schedule_reservation_jobs(updated_reservation)
                    logger.info(f"예약 ID {reservation_id} 승인으로 인한 스케줄링 작업 추가 완료")
                except Exception as e:
                    logger.error(f"예약 ID {reservation_id} 승인 중 오류 발생: {str(e)}")
                    import traceback
                    logger.error(f"상세 오류: {traceback.format_exc()}")
                    messages.error(request, _('예약 스케줄링 중 오류가 발생했습니다.'))
            
            # 상태가 승인됨에서 다른 상태로 변경된 경우 스케줄러에서 작업 제거
            elif old_status == 'approved' and updated_reservation.status != 'approved':
                try:
                    logger.info(f"예약 ID {reservation_id} 상태 변경으로 인한 스케줄링된 작업 취소 시작")
                    
                    # 서버 상태는 변경하지 않고 스케줄링된 작업만 취소
                    cancel_result = cancel_reservation_jobs(updated_reservation)
                    logger.info(f"예약 ID {reservation_id} 상태 변경으로 인한 스케줄링된 작업 취소 완료: {cancel_result}")
                except Exception as e:
                    logger.error(f"예약 ID {reservation_id} 상태 변경 중 오류 발생: {str(e)}")
                    import traceback
                    logger.error(f"상세 오류: {traceback.format_exc()}")
                    messages.error(request, _('예약 상태 변경 중 오류가 발생했습니다.'))
            
            messages.success(request, _('예약 상태가 업데이트되었습니다.'))
            return redirect('admin_reservation_list')
    else:
        form = ReservationAdminForm(instance=reservation)
    
    return render(request, 'server_manager/reservation/admin_update.html', {
        'form': form,
        'reservation': reservation
    })


@login_required
def instance_availability(request, instance_id):
    """
    인스턴스 예약 가능 시간 조회 API
    """
    instance = get_object_or_404(Instance, instance_id=instance_id)
    
    # 모든 예약 조회 (필터링 완화)
    now = timezone.now()
    # 과거 30일부터 미래 30일까지의 예약 조회
    start_date = now - timezone.timedelta(days=30)
    end_date = now + timezone.timedelta(days=30)
    
    # 디버깅을 위해 모든 예약 개수 로깅
    all_reservations_count = Reservation.objects.all().count()
    instance_reservations_count = Reservation.objects.filter(instance=instance).count()
    logger.info(f"전체 예약 수: {all_reservations_count}, 해당 인스턴스 예약 수: {instance_reservations_count}")
    
    reservations = Reservation.objects.filter(
        instance=instance,
        start_time__gte=start_date,
        end_time__lte=end_date
    ).values('id', 'start_time', 'end_time', 'user__username', 'status', 'purpose')
    
    reservation_list = list(reservations)
    
    # 필터링된 예약 수 로깅
    logger.info(f"필터링된 예약 수: {len(reservation_list)}")
    
    # 예약이 없는 경우 테스트 데이터 추가 (디버깅용)
    if len(reservation_list) == 0:
        logger.info("예약이 없어 테스트 데이터를 추가합니다.")
        # 현재 시간 기준으로 테스트 데이터 생성
        test_start = now + timezone.timedelta(hours=1)
        test_end = test_start + timezone.timedelta(hours=2)
        
        test_reservation = {
            'id': 999,
            'start_time': test_start,
            'end_time': test_end,
            'user__username': '테스트 사용자',
            'status': 'approved',
            'purpose': '테스트 예약'
        }
        reservation_list.append(test_reservation)
    
    # JSON 직렬화 가능한 형태로 변환 (KST 시간대로 강제 변환)
    kst = pytz.timezone('Asia/Seoul')
    for reservation in reservation_list:
        if isinstance(reservation['start_time'], datetime.datetime):
            # UTC 시간을 KST로 변환
            start_time_kst = reservation['start_time'].astimezone(kst)
            reservation['start_time'] = start_time_kst.strftime('%Y-%m-%dT%H:%M:%S%z')
        if isinstance(reservation['end_time'], datetime.datetime):
            # UTC 시간을 KST로 변환
            end_time_kst = reservation['end_time'].astimezone(kst)
            reservation['end_time'] = end_time_kst.strftime('%Y-%m-%dT%H:%M:%S%z')
        
        # 디버깅을 위해 시간 정보 로깅
        logger.info(f"예약 ID {reservation['id']} 시간: {reservation['start_time']} ~ {reservation['end_time']}")
    
    return JsonResponse({'reservations': reservation_list})


@login_required
def reservation_detail_api(request, reservation_id):
    """
    예약 상세 정보를 JSON으로 반환하는 API
    """
    if not request.user.is_admin:
        return JsonResponse({'error': '관리자만 접근할 수 있습니다.'}, status=403)
    
    try:
        reservation = Reservation.objects.get(id=reservation_id)
        
        # JSON으로 반환할 데이터 구성
        data = {
            'id': reservation.id,
            'user': {
                'username': reservation.user.username,
                'email': reservation.user.email
            },
            'instance': {
                'name': reservation.instance.name,
                'instance_id': reservation.instance.instance_id,
                'instance_type': reservation.instance.instance_type,
                'gpu_info': None
            },
            'start_time': reservation.start_time.isoformat(),
            'end_time': reservation.end_time.isoformat(),
            'created_at': reservation.created_at.isoformat(),
            'status': reservation.status,
            'purpose': reservation.purpose,
            'admin_comment': reservation.admin_comment
        }
        
        # GPU 정보가 있는 경우 추가
        if hasattr(reservation.instance, 'gpu_info') and reservation.instance.gpu_info:
            data['instance']['gpu_info'] = {
                'name': reservation.instance.gpu_info.name,
                'count': reservation.instance.gpu_info.count
            }
        
        return JsonResponse(data)
    except Reservation.DoesNotExist:
        return JsonResponse({'error': '예약을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def admin_reservation_update_api(request, reservation_id):
    """
    관리자용 예약 상태 업데이트 API (AJAX 요청 처리)
    """
    if not request.user.is_admin:
        return JsonResponse({'success': False, 'message': '관리자만 접근할 수 있습니다.'}, status=403)
    
    try:
        reservation = get_object_or_404(Reservation, id=reservation_id)
        
        if request.method == 'POST':
            try:
                data = json.loads(request.body)
                status = data.get('status')
                admin_comment = data.get('admin_comment', '')
                
                if status in ['pending', 'approved', 'rejected', 'canceled', 'completed']:
                    old_status = reservation.status
                    reservation.status = status
                    reservation.admin_comment = admin_comment
                    reservation.save()
                    
                    # 상태가 승인됨으로 변경된 경우 스케줄러에 작업 추가
                    if old_status != 'approved' and status == 'approved':
                        schedule_reservation_jobs(reservation)
                    # 상태가 승인됨에서 다른 상태로 변경된 경우 스케줄러에서 작업 제거
                    elif old_status == 'approved' and status != 'approved':
                        cancel_reservation_jobs(reservation)
                    
                    return JsonResponse({'success': True, 'message': '예약 상태가 업데이트되었습니다.'})
                else:
                    return JsonResponse({'success': False, 'message': '유효하지 않은 상태입니다.'}, status=400)
                    
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'message': '잘못된 JSON 형식입니다.'}, status=400)
        else:
            return JsonResponse({'success': False, 'message': '허용되지 않은 메서드입니다.'}, status=405)
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
