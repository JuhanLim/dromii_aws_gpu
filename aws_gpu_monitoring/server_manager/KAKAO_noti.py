"""
카카오톡 알림 서비스 - 네이버 클라우드 플랫폼 알림톡 API 사용
"""
import time
import hmac
import base64
import hashlib
import requests
import json
import logging
from datetime import datetime
from django.conf import settings
from decouple import config

logger = logging.getLogger(__name__)

class KakaoNotificationService:
    """
    카카오톡 알림 서비스 클래스
    """
    def __init__(self):
        # 환경 변수에서 API 키 및 설정 가져오기
        self.access_key = config('NCP_ACCESS_KEY')
        self.secret_key = config('NCP_SECRET_KEY')
        self.service_id = config('NCP_KAKAO_SERVICE_ID')
        self.api_url = f"https://sens.apigw.ntruss.com/alimtalk/v2/services/{self.service_id}/messages"
        
        # 알림톡 채널 정보
        self.plus_friend_id = '@드로미_dromii'  # 카카오톡 채널 ID
        self.template_code_admin = 'ReservationAdmin'  # 관리자용 템플릿 코드
        self.template_code_user = 'Reservation'  # 사용자용 템플릿 코드
        
        # API 키가 없으면 로그 출력
        if not self.access_key or not self.secret_key or not self.service_id:
            logger.warning("NCP 카카오톡 API 키가 설정되지 않았습니다.")
    
    def _make_signature(self, timestamp):
        """
        NCP API 요청을 위한 서명 생성
        """
        uri = f"/alimtalk/v2/services/{self.service_id}/messages"
        message = f"POST {uri}\n{timestamp}\n{self.access_key}"
        
        secret_key_bytes = bytes(self.secret_key, 'UTF-8')
        message = bytes(message, 'UTF-8')
        
        signing_key = base64.b64encode(hmac.new(secret_key_bytes, message, digestmod=hashlib.sha256).digest())
        
        return signing_key.decode('UTF-8')
    
    def send_alimtalk(self, phone_number, message, template_code):
        """
        카카오톡 알림톡 전송 메소드
        
        Args:
            phone_number (str): 수신자 전화번호 (예: '01012345678')
            message (str): 전송할 메시지 내용
            template_code (str): 사용할 템플릿 코드
        
        Returns:
            bool: 전송 성공 여부
        """
        if not self.access_key or not self.secret_key or not self.service_id:
            logger.error("NCP 카카오톡 API 키가 설정되지 않아 알림톡을 전송할 수 없습니다.")
            return False
        
        # 전화번호 형식 확인 및 변환 (하이픈 제거)
        phone_number = phone_number.replace('-', '')
        
        # 타임스탬프 생성
        timestamp = str(int(time.time() * 1000))
        
        # 요청 헤더
        headers = {
            'Content-Type': 'application/json; charset=UTF-8',
            'x-ncp-apigw-timestamp': timestamp,
            'x-ncp-iam-access-key': self.access_key,
            'x-ncp-apigw-signature-v2': self._make_signature(timestamp)
        }
        
        # 요청 데이터
        request_data = {
            'plusFriendId': self.plus_friend_id,
            'templateCode': template_code,
            'messages': [
                {
                    'to': phone_number,
                    'content': message,
                }
            ]
        }
        
        # 로그에 요청 데이터 기록 (민감 정보 제외)
        logger.info(f"카카오톡 알림톡 요청 데이터: 수신자={phone_number}, 메시지 길이={len(message)}")
        
        try:
            # API 요청
            logger.info(f"API 요청 URL: {self.api_url}")
            response = requests.post(
                self.api_url, 
                headers=headers, 
                data=json.dumps(request_data)
            )
            
            # 응답 처리
            if response.status_code == 202:
                result = response.json()
                logger.info(f"카카오톡 알림톡 전송 성공: {result}")
                return True
            else:
                logger.error(f"카카오톡 알림톡 전송 실패: {response.status_code}, {response.text}")
                return False
                
        except Exception as e:
            logger.exception("카카오톡 알림톡 전송 중 오류 발생")
            return False
    
    def to_admin_body(self, reservation):
        """
        관리자에게 보낼 예약 알림 메시지 생성
        
        Args:
            reservation: 예약 객체
        
        Returns:
            str: 메시지 내용
        """
        # 예약 날짜 포맷팅
        reservation_date = reservation.start_time.strftime('%Y-%m-%d %H:%M') if hasattr(reservation, 'start_time') else "지정된 날짜"
        
        return f"[드로미] GPU 서버 예약 발생\n\n{reservation.user.username}님의 예약이 신청되었습니다.\n{reservation_date}의 예약을 승인해 주십시오."
    
    def to_user_body(self, reservation):
        """
        사용자에게 보낼 예약 승인 알림 메시지 생성
        
        Args:
            reservation: 예약 객체
        
        Returns:
            str: 메시지 내용
        """
        # 예약 날짜 포맷팅
        reservation_date = reservation.start_time.strftime('%Y-%m-%d %H:%M') if hasattr(reservation, 'start_time') else "지정된 날짜"
        
        return f"[드로미] GPU 서버 예약 알림\n\n{reservation.user.username}님의 예약이 승인되었습니다.\n{reservation_date}에 예약하신 서버사용이 가능합니다."
    
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
            logger.error("관리자 전화번호가 설정되지 않아 카카오톡 알림톡을 전송할 수 없습니다.")
            return False
        
        # 메시지 내용 생성
        message = self.to_admin_body(reservation)
        
        # 카카오톡 알림톡 전송
        return self.send_alimtalk(admin_phone, message, self.template_code_admin)
    
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
            logger.error(f"사용자 {reservation.user.username}의 전화번호가 없어 카카오톡 알림톡을 전송할 수 없습니다.")
            return False
        
        # 메시지 내용 생성
        message = self.to_user_body(reservation)
        
        # 카카오톡 알림톡 전송
        return self.send_alimtalk(user_phone, message, self.template_code_user)

# 서비스 인스턴스 생성
kakao_service = KakaoNotificationService()
