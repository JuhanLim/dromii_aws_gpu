"""
카카오 알림톡 서비스
"""
import os
import json
import requests
import logging
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)

class KakaoNotificationService:
    """
    카카오 알림톡 서비스 클래스
    """
    def __init__(self):
        # 환경 변수에서 API 키 및 설정 가져오기
        self.api_key = os.environ.get('KAKAO_API_KEY', '')
        self.sender_key = os.environ.get('KAKAO_SENDER_KEY', '')
        self.template_code_reservation = os.environ.get('KAKAO_TEMPLATE_RESERVATION', '')
        self.template_code_approval = os.environ.get('KAKAO_TEMPLATE_APPROVAL', '')
        self.api_url = 'https://alimtalk-api.kakao.com/v2/sender/send'
        
        # API 키가 없으면 로그 출력
        if not self.api_key or not self.sender_key:
            logger.warning("카카오 API 키 또는 발신자 키가 설정되지 않았습니다.")
    
    def _send_notification(self, phone_number, template_code, template_data):
        """
        카카오 알림톡 전송 메소드
        
        Args:
            phone_number (str): 수신자 전화번호 (예: '01012345678')
            template_code (str): 알림톡 템플릿 코드
            template_data (dict): 템플릿에 들어갈 데이터
        
        Returns:
            bool: 전송 성공 여부
        """
        if not self.api_key or not self.sender_key:
            logger.error("카카오 API 키 또는 발신자 키가 설정되지 않아 알림톡을 전송할 수 없습니다.")
            return False
        
        # 전화번호 형식 확인 및 변환
        phone_number = phone_number.replace('-', '')
        if not phone_number.startswith('+82'):
            # 한국 번호인 경우 +82 형식으로 변환
            if phone_number.startswith('0'):
                phone_number = '+82' + phone_number[1:]
        
        # 요청 헤더
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        # 요청 데이터
        request_data = {
            'senderKey': self.sender_key,
            'templateCode': template_code,
            'messages': [
                {
                    'to': phone_number,
                    'templateData': json.dumps(template_data, ensure_ascii=False)
                }
            ]
        }
        
        try:
            # API 요청
            response = requests.post(
                self.api_url, 
                headers=headers, 
                data=json.dumps(request_data, ensure_ascii=False).encode('utf-8')
            )
            
            # 응답 처리
            if response.status_code == 200:
                result = response.json()
                logger.info(f"카카오 알림톡 전송 성공: {result}")
                return True
            else:
                logger.error(f"카카오 알림톡 전송 실패: {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"카카오 알림톡 전송 중 오류 발생: {str(e)}")
            return False
    
    def send_reservation_notification_to_admin(self, reservation):
        """
        관리자에게 새로운 예약 알림 전송
        
        Args:
            reservation: 예약 객체
        
        Returns:
            bool: 전송 성공 여부
        """
        # 관리자 전화번호 (환경 변수에서 가져오기)
        admin_phone = os.environ.get('ADMIN_PHONE_NUMBER', '')
        if not admin_phone:
            logger.error("관리자 전화번호가 설정되지 않아 알림톡을 전송할 수 없습니다.")
            return False
        
        # 템플릿 데이터 구성
        template_data = {
            'user_name': reservation.user.username,
            'instance_name': reservation.instance.name,
            'start_time': reservation.start_time.strftime('%Y년 %m월 %d일 %H시 %M분'),
            'end_time': reservation.end_time.strftime('%Y년 %m월 %d일 %H시 %M분'),
            'purpose': reservation.purpose
        }
        
        # 알림톡 전송
        return self._send_notification(admin_phone, self.template_code_reservation, template_data)
    
    def send_approval_notification_to_user(self, reservation):
        """
        사용자에게 예약 승인 알림 전송
        
        Args:
            reservation: 예약 객체
        
        Returns:
            bool: 전송 성공 여부
        """
        # 사용자 전화번호 (사용자 모델에서 직접 가져오기)
        user_phone = reservation.user.phone_number
        if not user_phone:
            logger.error(f"사용자 {reservation.user.username}의 전화번호가 없어 알림톡을 전송할 수 없습니다.")
            return False
        
        # 템플릿 데이터 구성
        template_data = {
            'user_name': reservation.user.username,
            'instance_name': reservation.instance.name,
            'start_time': reservation.start_time.strftime('%Y년 %m월 %d일 %H시 %M분'),
            'end_time': reservation.end_time.strftime('%Y년 %m월 %d일 %H시 %M분'),
            'purpose': reservation.purpose
        }
        
        # 알림톡 전송
        return self._send_notification(user_phone, self.template_code_approval, template_data)

# 서비스 인스턴스 생성
kakao_service = KakaoNotificationService()