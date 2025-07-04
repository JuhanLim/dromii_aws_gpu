from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
import logging
import datetime

from .cost_service import get_costs, get_instance_costs

logger = logging.getLogger(__name__)

@staff_member_required
def cost_dashboard(request):
    """
    AWS 비용 대시보드 - 관리자 전용
    """
    try:
        # 기본 날짜 범위 설정 (지난 30일)
        end_date = datetime.datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        
        # 요청에서 날짜 범위 가져오기
        if request.method == 'POST':
            start_date = request.POST.get('start_date', start_date)
            end_date = request.POST.get('end_date', end_date)
        
        # 비용 데이터 가져오기
        costs = get_costs(start_date, end_date, 'DAILY')
        instance_costs = get_instance_costs(start_date, end_date)
        
        context = {
            'costs': costs,
            'instance_costs': instance_costs,
            'start_date': start_date,
            'end_date': end_date,
            'title': _('AWS 비용 대시보드'),
            'active_menu': 'costs'
        }
        
        return render(request, 'server_manager/costs/dashboard.html', context)
    except Exception as e:
        logger.error(f"비용 대시보드 로딩 중 오류: {str(e)}")
        return render(request, 'server_manager/costs/dashboard.html', {
            'error': str(e),
            'title': _('AWS 비용 대시보드'),
            'active_menu': 'costs'
        })

@staff_member_required
def cost_api(request):
    """
    AWS 비용 API - 관리자 전용
    """
    try:
        # 날짜 범위 가져오기
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        granularity = request.GET.get('granularity', 'DAILY')
        
        # 비용 데이터 가져오기
        costs = get_costs(start_date, end_date, granularity)
        
        return JsonResponse({
            'success': True,
            'data': costs
        })
    except Exception as e:
        logger.error(f"비용 API 호출 중 오류: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

@staff_member_required
def instance_cost_api(request):
    """
    EC2 인스턴스별 비용 API - 관리자 전용
    """
    try:
        # 날짜 범위 가져오기
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # 인스턴스별 비용 데이터 가져오기
        costs = get_instance_costs(start_date, end_date)
        
        return JsonResponse({
            'success': True,
            'data': costs
        })
    except Exception as e:
        logger.error(f"인스턴스별 비용 API 호출 중 오류: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)