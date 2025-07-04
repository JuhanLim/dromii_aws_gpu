import boto3
import logging
import datetime
from decimal import Decimal
import requests
from django.conf import settings
from decouple import config

logger = logging.getLogger(__name__)

def get_cost_explorer_client():
    """
    AWS Cost Explorer 클라이언트 생성
    """
    try:
        return boto3.client(
            'ce', 
            region_name=config('AWS_DEFAULT_REGION', default='us-east-1'),
            aws_access_key_id=config('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=config('AWS_SECRET_ACCESS_KEY')
        )
    except Exception as e:
        logger.error(f"Cost Explorer 클라이언트 생성 중 오류 발생: {str(e)}")
        return None

def get_exchange_rate():
    """
    달러-원화 환율 정보 가져오기
    기본값: 1 USD = 1350 KRW
    """
    try:
        # 환율 API 호출 (예: 한국은행 API 또는 다른 무료 API)
        response = requests.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=5)
        data = response.json()
        
        # KRW 환율 가져오기
        if 'rates' in data and 'KRW' in data['rates']:
            return Decimal(str(data['rates']['KRW']))
        else:
            logger.warning("환율 정보를 가져올 수 없습니다. 기본값 사용")
            return Decimal('1350')
    except Exception as e:
        logger.error(f"환율 정보 조회 중 오류 발생: {str(e)}")
        return Decimal('1350')  # 기본값

def get_costs(start_date=None, end_date=None, granularity='DAILY'):
    """
    AWS Cost Explorer API를 사용하여 비용 정보 조회
    
    Args:
        start_date (str): 시작 날짜 (YYYY-MM-DD)
        end_date (str): 종료 날짜 (YYYY-MM-DD)
        granularity (str): 데이터 세분화 (DAILY, MONTHLY)
        
    Returns:
        dict: 비용 정보
    """
    try:
        client = get_cost_explorer_client()
        if not client:
            return {'error': 'Cost Explorer 클라이언트를 생성할 수 없습니다.'}
        
        # 날짜 설정 (기본값: 지난 30일)
        if not start_date:
            start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Cost Explorer API 호출
        response = client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity=granularity,
            Metrics=['UnblendedCost'],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }
            ]
        )
        
        # 환율 정보 가져오기
        exchange_rate = get_exchange_rate()
        
        # 결과 처리
        result = {
            'start_date': start_date,
            'end_date': end_date,
            'granularity': granularity,
            'exchange_rate': float(exchange_rate),
            'time_periods': [],
            'services': {},
            'total_usd': 0,
            'total_krw': 0
        }
        
        # 날짜별 데이터 처리
        for time_period in response.get('ResultsByTime', []):
            period = {
                'start': time_period['TimePeriod']['Start'],
                'end': time_period['TimePeriod']['End'],
                'services': {}
            }
            
            period_total_usd = 0
            
            # 서비스별 비용 처리
            for group in time_period.get('Groups', []):
                service_name = group['Keys'][0]
                amount = float(group['Metrics']['UnblendedCost']['Amount'])
                unit = group['Metrics']['UnblendedCost']['Unit']
                
                period['services'][service_name] = {
                    'amount_usd': amount,
                    'amount_krw': amount * float(exchange_rate),
                    'unit': unit
                }
                
                period_total_usd += amount
                
                # 전체 서비스 통계 업데이트
                if service_name not in result['services']:
                    result['services'][service_name] = {
                        'total_usd': 0,
                        'total_krw': 0
                    }
                
                result['services'][service_name]['total_usd'] += amount
                result['services'][service_name]['total_krw'] += amount * float(exchange_rate)
            
            # 기간별 총액 추가
            period['total_usd'] = period_total_usd
            period['total_krw'] = period_total_usd * float(exchange_rate)
            
            result['time_periods'].append(period)
            result['total_usd'] += period_total_usd
            
        # 전체 원화 금액 계산
        result['total_krw'] = result['total_usd'] * float(exchange_rate)
        
        return result
    except Exception as e:
        logger.error(f"비용 정보 조회 중 오류 발생: {str(e)}")
        return {'error': str(e)}

def get_instance_costs(start_date=None, end_date=None):
    """
    EC2 인스턴스별 비용 정보 조회
    
    Args:
        start_date (str): 시작 날짜 (YYYY-MM-DD)
        end_date (str): 종료 날짜 (YYYY-MM-DD)
        
    Returns:
        dict: 인스턴스별 비용 정보
    """
    try:
        client = get_cost_explorer_client()
        if not client:
            return {'error': 'Cost Explorer 클라이언트를 생성할 수 없습니다.'}
        
        # 날짜 설정 (기본값: 지난 30일)
        if not start_date:
            start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        # Cost Explorer API 호출
        response = client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'INSTANCE_TYPE'
                }
            ],
            Filter={
                'Dimensions': {
                    'Key': 'SERVICE',
                    'Values': ['Amazon Elastic Compute Cloud - Compute']
                }
            }
        )
        
        # 환율 정보 가져오기
        exchange_rate = get_exchange_rate()
        
        # 결과 처리
        result = {
            'start_date': start_date,
            'end_date': end_date,
            'exchange_rate': float(exchange_rate),
            'instances': {},
            'total_usd': 0,
            'total_krw': 0
        }
        
        # 인스턴스별 비용 처리
        for time_period in response.get('ResultsByTime', []):
            for group in time_period.get('Groups', []):
                instance_type = group['Keys'][0]
                amount = float(group['Metrics']['UnblendedCost']['Amount'])
                
                if instance_type not in result['instances']:
                    result['instances'][instance_type] = {
                        'total_usd': 0,
                        'total_krw': 0
                    }
                
                result['instances'][instance_type]['total_usd'] += amount
                result['instances'][instance_type]['total_krw'] += amount * float(exchange_rate)
                result['total_usd'] += amount
        
        # 전체 원화 금액 계산
        result['total_krw'] = result['total_usd'] * float(exchange_rate)
        
        return result
    except Exception as e:
        logger.error(f"인스턴스별 비용 정보 조회 중 오류 발생: {str(e)}")
        return {'error': str(e)}