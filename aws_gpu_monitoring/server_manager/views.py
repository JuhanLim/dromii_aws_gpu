from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
import json
import logging

from .ec2_service import EC2Service
from .models.instance import Instance

# EC2 서비스 인스턴스 생성
ec2_service = EC2Service()

# 대시보드 - 인스턴스 목록 표시
def dashboard(request):
    """
    EC2 인스턴스 목록을 보여주는 대시보드 페이지
    """
    try:
        # EC2 인스턴스 목록 조회
        response = ec2_service.list_instances()
        
        if response['success']:
            instances = response['data']
            context = {
                'instances': instances,
                'title': 'AWS GPU 인스턴스 대시보드',
                'active_menu': 'dashboard'
            }
            return render(request, 'server_manager/dashboard.html', context)
        else:
            messages.error(request, f'인스턴스 목록 조회 실패: {response["message"]}')  
            return render(request, 'server_manager/dashboard.html', {
                'error': response['message'],
                'title': 'AWS GPU 인스턴스 대시보드',
                'active_menu': 'dashboard'
            })
    except Exception as e:
        logging.error(f"대시보드 로딩 중 오류: {str(e)}")
        messages.error(request, f'오류가 발생했습니다: {str(e)}')
        return render(request, 'server_manager/dashboard.html', {
            'error': str(e),
            'title': 'AWS GPU 인스턴스 대시보드',
            'active_menu': 'dashboard'
        })

# 인스턴스 상세 정보 페이지
def instance_detail(request, instance_id):
    """
    특정 EC2 인스턴스의 상세 정보를 보여주는 페이지
    """
    try:
        # 인스턴스 상태 조회
        response = ec2_service.get_instance_status(instance_id)
        
        if response['success']:
            instance_data = response['data']
            
            # GPU 정보 조회
            gpu_response = ec2_service.get_gpu_info(instance_id)
            if gpu_response['success']:
                instance_data['gpu_info'] = gpu_response['data']['gpu_info']
            
            context = {
                'instance': instance_data,
                'title': f'인스턴스 상세 정보 - {instance_id}',
                'active_menu': 'instances'
            }
            return render(request, 'server_manager/instance_detail.html', context)
        else:
            messages.error(request, f'인스턴스 정보 조회 실패: {response["message"]}')  
            return redirect('dashboard')
    except Exception as e:
        logging.error(f"인스턴스 상세 정보 로딩 중 오류: {str(e)}")
        messages.error(request, f'오류가 발생했습니다: {str(e)}')
        return redirect('dashboard')

# 인스턴스 제어 API 엔드포인트
@require_http_methods(["POST"])
def control_instance(request):
    """
    EC2 인스턴스 제어 API (시작, 중지, 재부팅, 종료)
    """
    try:
        data = json.loads(request.body)
        instance_id = data.get('instance_id')
        action = data.get('action')
        
        if not instance_id or not action:
            return JsonResponse({
                'success': False,
                'message': '인스턴스 ID와 작업 유형이 필요합니다.'
            }, status=400)
        
        # 작업 유형에 따른 처리
        if action == 'start':
            response = ec2_service.start_instance(instance_id)
        elif action == 'stop':
            response = ec2_service.stop_instance(instance_id)
        elif action == 'reboot':
            response = ec2_service.reboot_instance(instance_id)
        elif action == 'terminate':
            response = ec2_service.terminate_instance(instance_id)
        else:
            return JsonResponse({
                'success': False,
                'message': f'지원하지 않는 작업 유형입니다: {action}'
            }, status=400)
        
        return JsonResponse(response)
    except Exception as e:
        logging.error(f"인스턴스 제어 중 오류: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'오류가 발생했습니다: {str(e)}'
        }, status=500)

# 인스턴스 생성 페이지
def create_instance_form(request):
    """
    새 EC2 인스턴스 생성 폼 페이지
    """
    context = {
        'title': '새 인스턴스 생성',
        'active_menu': 'create_instance'
    }
    return render(request, 'server_manager/create_instance.html', context)

# 인스턴스 생성 처리
@require_http_methods(["POST"])
def create_instance(request):
    """
    새 EC2 인스턴스 생성 처리
    """
    try:
        ami_id = request.POST.get('ami_id')
        instance_type = request.POST.get('instance_type')
        key_name = request.POST.get('key_name')
        name = request.POST.get('name', '')
        
        # 필수 파라미터 검증
        if not ami_id or not instance_type or not key_name:
            messages.error(request, '필수 정보가 누락되었습니다.')
            return redirect('create_instance_form')
        
        # 보안 그룹 및 서브넷 (선택 사항)
        security_group_ids = request.POST.get('security_group_ids', '').split(',')
        security_group_ids = [sg.strip() for sg in security_group_ids if sg.strip()]
        subnet_id = request.POST.get('subnet_id', None)
        
        # 태그 설정
        tags = [{'Key': 'Name', 'Value': name}] if name else []
        
        # 인스턴스 생성 요청
        response = ec2_service.create_instance(
            ami_id=ami_id,
            instance_type=instance_type,
            key_name=key_name,
            security_group_ids=security_group_ids if security_group_ids else None,
            subnet_id=subnet_id,
            tags=tags
        )
        
        if response['success']:
            messages.success(request, f'인스턴스가 성공적으로 생성되었습니다: {response["data"]["instance_id"]}')
            return redirect('dashboard')
        else:
            messages.error(request, f'인스턴스 생성 실패: {response["message"]}')
            return redirect('create_instance_form')
    except Exception as e:
        logging.error(f"인스턴스 생성 중 오류: {str(e)}")
        messages.error(request, f'오류가 발생했습니다: {str(e)}')
        return redirect('create_instance_form')

# 인스턴스 상태 확인 API
@require_http_methods(["GET"])
def check_instance_status(request, instance_id):
    """
    EC2 인스턴스 상태 확인 API (AJAX 요청용)
    """
    try:
        response = ec2_service.get_instance_status(instance_id)
        return JsonResponse(response)
    except Exception as e:
        logging.error(f"인스턴스 상태 확인 중 오류: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'오류가 발생했습니다: {str(e)}'
        }, status=500)

# 태그 관리 API
@require_http_methods(["POST"])
def manage_tags(request):
    """
    EC2 인스턴스 태그 관리 API
    """
    try:
        data = json.loads(request.body)
        instance_id = data.get('instance_id')
        tags = data.get('tags', [])
        action = data.get('action', 'create')
        
        if not instance_id or not tags:
            return JsonResponse({
                'success': False,
                'message': '인스턴스 ID와 태그 정보가 필요합니다.'
            }, status=400)
        
        response = ec2_service.manage_tags(instance_id, tags, action)
        return JsonResponse(response)
    except Exception as e:
        logging.error(f"태그 관리 중 오류: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'오류가 발생했습니다: {str(e)}'
        }, status=500)
