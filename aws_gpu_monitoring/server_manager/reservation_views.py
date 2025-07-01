from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q

from .models import Instance, Reservation
from .forms import ReservationForm, ReservationAdminForm


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
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
    
    if reservation.status == 'approved' and reservation.is_active():
        messages.error(request, _('현재 사용 중인 예약은 취소할 수 없습니다.'))
        return redirect('reservation_list')
    
    reservation.status = 'canceled'
    reservation.save()
    
    messages.success(request, _('예약이 취소되었습니다.'))
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
    
    if request.method == 'POST':
        form = ReservationAdminForm(request.POST, instance=reservation)
        if form.is_valid():
            form.save()
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
    
    # 오늘부터 30일 이내의 승인된 예약 조회
    now = timezone.now()
    end_date = now + timezone.timedelta(days=30)
    
    reservations = Reservation.objects.filter(
        instance=instance,
        status='approved',
        start_time__gte=now,
        start_time__lte=end_date
    ).values('start_time', 'end_time', 'user__username')
    
    return JsonResponse(list(reservations), safe=False)
