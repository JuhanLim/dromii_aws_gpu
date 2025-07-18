"""
SMS 알림 서비스 - 네이버 클라우드 플랫폼 SMS API 사용
"""
import os
import time
import hmac
import base64
import hashlib
import requests
import json
import logging
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)

class SMSNotificationService:
    """
    SMS 알림 서비스 클래스
    """
    def __init__(self):
        # 환경 변수에서 API 키 및 설정 가져오기
        self.access_key = config('NCP_ACCESS_KEY')
        self.secret_key = config('NCP_SECRET_KEY')
        self.service_id = config('NCP_SERVICE_ID')
        self.api_url = f"https://sens.apigw.ntruss.com/sms/v2/services/{self.service_id}/messages"
        
        # API 키가 없으면 로그 출력
        if not self.access_key or not self.secret_key or not self.service_id:
            logger.warning("NCP SMS API 키가 설정되지 않았습니다.")
    
    def _make_signature(self, timestamp):
        """
        NCP API 요청을 위한 서명 생성
        """
        method = "POST"
        uri = f"/sms/v2/services/{self.service_id}/messages"
        
        message = method + " " + uri + "\n" + timestamp + "\n" + self.access_key
        message = bytes(message, 'UTF-8')
        
        secret_key_bytes = bytes(self.secret_key, 'UTF-8')
        signing_key = base64.b64encode(hmac.new(secret_key_bytes, message, digestmod=hashlib.sha256).digest())
        
        return signing_key.decode('UTF-8')
    
    def send_sms(self, phone_number, message):
        """
        SMS 전송 메소드
        
        Args:
            phone_number (str): 수신자 전화번호 (예: '01012345678')
            message (str): 전송할 메시지 내용
        
        Returns:
            bool: 전송 성공 여부
        """
        if not self.access_key or not self.secret_key or not self.service_id:
            logger.error("NCP SMS API 키가 설정되지 않아 SMS를 전송할 수 없습니다.")
            return False
        
        # 전화번호 형식 확인 및 변환
        phone_number = phone_number.replace('-', '')
        if not phone_number.startswith('+82') and phone_number.startswith('0'):
            # 한국 번호인 경우 +82 형식으로 변환
            phone_number = '+82' + phone_number[1:]
        
        timestamp = str(int(time.time() * 1000))
        
        # 요청 헤더
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'x-ncp-apigw-timestamp': timestamp,
            'x-ncp-iam-access-key': self.access_key,
            'x-ncp-apigw-signature-v2': self._make_signature(timestamp)
        }
        
        # 요청 데이터
        request_data = {
            'type': 'SMS',
            'contentType': 'COMM',
            'countryCode': '82',
            'from': '01062664396',  # 발신번호 (실제 등록된 번호로 변경 필요)
            'content': message,
            'messages': [
                {
                    'to': phone_number
                }
            ]
        }
        
        try:
            # API 요청
            response = requests.post(
                self.api_url, 
                headers=headers, 
                data=json.dumps(request_data)
            )
            
            # 응답 처리
            if response.status_code == 202:
                result = response.json()
                logger.info(f"SMS 전송 성공: {result}")
                return True
            else:
                logger.error(f"SMS 전송 실패: {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"SMS 전송 중 오류 발생: {str(e)}")
            return False
    
    def to_admin_body(self, reservation):
        """
        관리자에게 보낼 예약 알림 메시지 생성
        
        Args:
            reservation: 예약 객체
        
        Returns:
            str: 메시지 내용
        """
        return f"[드로미 GPU 서버 예약 알림]\n\n" \
               f"사용자: {reservation.user.username}\n" \
            #    f"인스턴스: {reservation.instance.name}\n" \
            #    f"시작 시간: {reservation.start_time.strftime('%Y-%m-%d %H:%M')}\n" \
            #    f"종료 시간: {reservation.end_time.strftime('%Y-%m-%d %H:%M')}\n" \
            #    f"목적: {reservation.purpose}\n\n" \
               f"관리자 페이지에서 승인해주세요."
    
    def to_user_body(self, reservation):
        """
        사용자에게 보낼 예약 승인 알림 메시지 생성
        
        Args:
            reservation: 예약 객체
        
        Returns:
            str: 메시지 내용
        """
        return f"[드로미 GPU 서버 예약 승인 알림]\n\n" \
               f"{reservation.user.username}님의 예약이 승인되었습니다.\n\n" #\
            #    f"인스턴스: {reservation.instance.name}\n" \
            #    f"시작 시간: {reservation.start_time.strftime('%Y-%m-%d %H:%M')}\n" \
            #    f"종료 시간: {reservation.end_time.strftime('%Y-%m-%d %H:%M')}\n" \
            #    f"목적: {reservation.purpose}\n\n" \
            #    f"예약된 시간에 자동으로 인스턴스가 시작됩니다."
    
    def send_reservation_notification_to_admin(self, reservation):
        """
        관리자에게 새로운 예약 알림 전송
        
        Args:
            reservation: 예약 객체
        
        Returns:
            bool: 전송 성공 여부
        """
        # 관리자 전화번호 (환경 변수에서 가져오기)
        admin_phone = config('ADMIN_PHONE_NUMBER')
        if not admin_phone:
            logger.error("관리자 전화번호가 설정되지 않아 SMS를 전송할 수 없습니다.")
            return False
        
        # 메시지 내용 생성
        message = self.to_admin_body(reservation)
        
        # SMS 전송
        return self.send_sms(admin_phone, message)
    
    def send_approval_notification_to_user(self, reservation):
        """
        사용자에게 예약 승인 알림 전송
        
        Args:
            reservation: 예약 객체
        
        Returns:
            bool: 전송 성공 여부
        """
        # 사용자 전화번호 (User 모델에서 가져오기)
        user_phone = reservation.user.phone_number
        if not user_phone:
            logger.error(f"사용자 {reservation.user.username}의 전화번호가 없어 SMS를 전송할 수 없습니다.")
            return False
        
        # 메시지 내용 생성
        message = self.to_user_body(reservation)
        
        # SMS 전송
        return self.send_sms(user_phone, message)

# 서비스 인스턴스 생성
sms_service = SMSNotificationService()