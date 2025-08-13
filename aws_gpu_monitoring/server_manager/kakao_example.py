import time
import uuid
import hmac
import hashlib
import base64
import requests
import json

# 인증 정보 설정
access_key = config('NCP_ACCESS_KEY')
secret_key = config('NCP_SECRET_KEY')
service_id = config('NCP_KAKAO_SERVICE_ID')

# 알림톡 채널 정보
plus_friend_id = '@드로미_dromii'  # 카카오톡 채널 ID (@없이 입력)
template_code = 'ReservationAdmin'  # 사전에 등록된 템플릿 코드 . 유저에겐 Reservation 사용자에겐 ReservationAdmin

# 요청 URL (알림톡 v2 API)
url = f"https://sens.apigw.ntruss.com/alimtalk/v2/services/{service_id}/messages"
timestamp = str(int(time.time() * 1000))
uri = f"/alimtalk/v2/services/{service_id}/messages"

# 서명 생성 함수
def make_signature(uri, timestamp, access_key, secret_key):
    message = f"POST {uri}\n{timestamp}\n{access_key}"
    secret_key = bytes(secret_key, 'UTF-8')
    message = bytes(message, 'UTF-8')
    signingKey = base64.b64encode(hmac.new(secret_key, message, digestmod=hashlib.sha256).digest())
    return signingKey.decode('UTF-8')

def send_alimtalk(phone_number, name=None, date=None):
    """
    카카오 알림톡 발송 함수
    
    Args:
        phone_number (str): 수신자 전화번호 (하이픈 없이)
        name (str): 수신자 이름
        date (str): 예약 날짜
    
    Returns:
        dict: API 응답 결과
    """
    # 타임스탬프 갱신 (함수 호출 시점 기준)
    timestamp = str(int(time.time() * 1000))
    
    # 변수 값이 없는 경우 기본값 설정
    name = name or "고객"
    date = date or "지정된 날짜"
    
    # f-string으로 변수 직접 대체
    content = f"[드로미] GPU 서버 예약 알림\n\n{name}님의 예약이 승인되었습니다.\n{date}에 예약하신 서버사용이 가능합니다."
    content_admin = f"[드로미] GPU 서버 예약 발생\n\n{name}님의 예약이 신청되었습니다.\n{date}의 예약을 승인해 주십시오."
    # 메시지 본문
    body = {
        "plusFriendId": plus_friend_id,
        "templateCode": template_code,
        "messages": [
            {
                "to": phone_number,
                "content": content_admin,
            }
        ]
    }
    
    # 헤더 설정
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "x-ncp-apigw-timestamp": timestamp,
        "x-ncp-iam-access-key": access_key,
        "x-ncp-apigw-signature-v2": make_signature(uri, timestamp, access_key, secret_key)
    }
    
    # 요청 전송
    response = requests.post(url, headers=headers, data=json.dumps(body))
    
    # 응답 결과 반환
    return {
        "status_code": response.status_code,
        "response": response.json()
    }

# 사용 예시
if __name__ == "__main__":
    # 수신자 번호
    recipient = "01051323777"
    
    # 이름과 날짜 직접 전달
    name = "임주한"
    date = "2025-07-28"
    
    # 알림톡 발송
    result = send_alimtalk(recipient, name, date)
    
    # 결과 출력
    print(f"상태 코드: {result['status_code']}")
    print(f"응답 내용: {result['response']}")
