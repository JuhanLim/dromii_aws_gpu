import boto3
import json
import logging
from datetime import datetime
from decouple import config
from django.db import transaction
from server_manager.models.instance import Instance

class EC2Service:
    def __init__(self):
        self.ec2_client = boto3.client('ec2', 
                               aws_access_key_id=config('AWS_ACCESS_KEY_ID'),
                               aws_secret_access_key=config('AWS_SECRET_ACCESS_KEY'),
                               region_name=config('AWS_DEFAULT_REGION', default='ap-northeast-2'))
        self.ec2_resource = boto3.resource('ec2',
                               aws_access_key_id=config('AWS_ACCESS_KEY_ID'),
                               aws_secret_access_key=config('AWS_SECRET_ACCESS_KEY'),
                               region_name=config('AWS_DEFAULT_REGION', default='ap-northeast-2'))
    
    def start_instance(self, instance_id):
        """
        EC2 인스턴스를 시작합니다.
        
        Args:
            instance_id (str): 시작할 EC2 인스턴스의 ID
            
        Returns:
            dict: AWS API 응답
        """
        try:
            response = self.ec2_client.start_instances(InstanceIds=[instance_id])
            # 데이터베이스 업데이트
            self._update_instance_state(instance_id, 'pending')
            # 인스턴스가 성공적으로 시작되면 재시작 시도 횟수 초기화
            self._reset_restart_attempts(instance_id)
            return {
                'success': True,
                'message': f'인스턴스 {instance_id} 시작 요청이 성공적으로 처리되었습니다.',
                'data': response
            }
        except Exception as e:
            error_msg = str(e)
            # Spot 인스턴스 용량 부족 오류 확인
            if 'there is no available Spot capacity' in error_msg:
                # 자동 재시작 시도
                auto_restart_response = self._handle_auto_restart(instance_id)
                if auto_restart_response['auto_restart_initiated']:
                    return {
                        'success': False,
                        'message': f'Spot 용량 부족으로 인스턴스 시작 실패. 자동 재시작이 예약되었습니다. 재시작 시도 횟수: {auto_restart_response["restart_attempts"]}',
                        'error': error_msg,
                        'auto_restart': auto_restart_response
                    }
            
            return {
                'success': False,
                'message': f'인스턴스 시작 중 오류가 발생했습니다: {error_msg}',
                'error': error_msg
            }
    
    def stop_instance(self, instance_id):
        """
        EC2 인스턴스를 중지합니다.
        
        Args:
            instance_id (str): 중지할 EC2 인스턴스의 ID
            
        Returns:
            dict: AWS API 응답
        """
        try:
            # 먼저 인스턴스 상태 확인
            logging.info(f"인스턴스 {instance_id} 중지 요청 전 상태 확인")
            try:
                status_response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
                current_state = status_response['Reservations'][0]['Instances'][0]['State']['Name']
                logging.info(f"인스턴스 {instance_id}의 현재 상태: {current_state}")
                
                # 이미 중지된 상태인지 확인
                if current_state in ['stopped', 'stopping']:
                    logging.info(f"인스턴스 {instance_id}는 이미 {current_state} 상태입니다.")
                    self._update_instance_state(instance_id, current_state)
                    return {
                        'success': True,
                        'message': f'인스턴스 {instance_id}는 이미 {current_state} 상태입니다.',
                        'data': {'State': {'Name': current_state}}
                    }
            except Exception as status_error:
                logging.warning(f"인스턴스 상태 확인 중 오류: {str(status_error)}")
            
            # 인스턴스 중지 요청
            logging.info(f"인스턴스 {instance_id} 중지 요청 시작")
            response = self.ec2_client.stop_instances(InstanceIds=[instance_id])
            logging.info(f"인스턴스 {instance_id} 중지 요청 응답: {response}")
            
            # 데이터베이스 업데이트
            self._update_instance_state(instance_id, 'stopping')
            
            return {
                'success': True,
                'message': f'인스턴스 {instance_id} 중지 요청이 성공적으로 처리되었습니다.',
                'data': response
            }
        except Exception as e:
            logging.error(f"인스턴스 {instance_id} 중지 중 오류 발생: {str(e)}")
            import traceback
            logging.error(f"상세 오류: {traceback.format_exc()}")
            return {
                'success': False,
                'message': f'인스턴스 중지 중 오류가 발생했습니다: {str(e)}',
                'error': str(e)
            }
    
    def get_instance_status(self, instance_id):
        """
        EC2 인스턴스의 상태를 조회합니다.
        
        Args:
            instance_id (str): 상태를 조회할 EC2 인스턴스의 ID
            
        Returns:
            dict: 인스턴스 상태 정보
        """
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance_data = response['Reservations'][0]['Instances'][0]
            state = instance_data['State']['Name']
            
            # 데이터베이스 업데이트
            self._update_instance_state(instance_id, state)
            
            return {
                'success': True,
                'message': f'인스턴스 {instance_id} 상태 조회가 성공적으로 처리되었습니다.',
                'data': {
                    'instance_id': instance_id,
                    'state': state,
                    'instance_type': instance_data.get('InstanceType', ''),
                    'public_ip': instance_data.get('PublicIpAddress', ''),
                    'private_ip': instance_data.get('PrivateIpAddress', ''),
                    'launch_time': instance_data.get('LaunchTime', '').isoformat() if 'LaunchTime' in instance_data else '',
                }
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'인스턴스 상태 조회 중 오류가 발생했습니다: {str(e)}',
                'error': str(e)
            }
            
    def list_instances(self, filters=None):
        """
        EC2 인스턴스 목록을 조회합니다.
        
        Args:
            filters (list, optional): 인스턴스 필터링 조건
            
        Returns:
            dict: 인스턴스 목록 정보
        """
        try:
            if filters:
                response = self.ec2_client.describe_instances(Filters=filters)
            else:
                response = self.ec2_client.describe_instances()
                
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    # 태그에서 이름 추출
                    name = ''
                    if 'Tags' in instance:
                        for tag in instance['Tags']:
                            if tag['Key'] == 'Name':
                                name = tag['Value']
                                break
                    
                    # GPU 정보 추출 (인스턴스 타입에 따라 결정)
                    gpu_info = self._get_gpu_info_by_instance_type(instance['InstanceType'])
                    
                    instance_data = {
                        'instance_id': instance['InstanceId'],
                        'name': name,
                        'instance_type': instance['InstanceType'],
                        'state': instance['State']['Name'],
                        'public_ip': instance.get('PublicIpAddress', ''),
                        'private_ip': instance.get('PrivateIpAddress', ''),
                        'launch_time': instance.get('LaunchTime', '').isoformat() if 'LaunchTime' in instance else '',
                        'gpu_info': gpu_info
                    }
                    instances.append(instance_data)
                    
                    # 데이터베이스 동기화
                    self._sync_instance_to_db(instance_data)
            
            return {
                'success': True,
                'message': f'{len(instances)}개의 인스턴스를 조회했습니다.',
                'data': instances
            }
        except Exception as e:
            logging.error(f"인스턴스 목록 조회 중 오류: {str(e)}")
            return {
                'success': False,
                'message': f'인스턴스 목록 조회 중 오류가 발생했습니다: {str(e)}',
                'error': str(e)
            }
    
    def create_instance(self, ami_id, instance_type, key_name, security_group_ids=None, subnet_id=None, tags=None, user_data=None):
        """
        새로운 EC2 인스턴스를 생성합니다.
        
        Args:
            ami_id (str): 사용할 AMI ID
            instance_type (str): 인스턴스 타입 (예: t2.micro, g4dn.xlarge 등)
            key_name (str): 사용할 키 페어 이름
            security_group_ids (list, optional): 보안 그룹 ID 목록
            subnet_id (str, optional): 서브넷 ID
            tags (list, optional): 인스턴스에 적용할 태그 목록
            user_data (str, optional): 인스턴스 시작 시 실행할 스크립트
            
        Returns:
            dict: 생성된 인스턴스 정보
        """
        try:
            run_instances_args = {
                'ImageId': ami_id,
                'InstanceType': instance_type,
                'KeyName': key_name,
                'MinCount': 1,
                'MaxCount': 1
            }
            
            if security_group_ids:
                run_instances_args['SecurityGroupIds'] = security_group_ids
                
            if subnet_id:
                run_instances_args['SubnetId'] = subnet_id
                
            if user_data:
                run_instances_args['UserData'] = user_data
                
            response = self.ec2_client.run_instances(**run_instances_args)
            
            instance = response['Instances'][0]
            instance_id = instance['InstanceId']
            
            # 태그 추가
            if tags:
                self.ec2_client.create_tags(
                    Resources=[instance_id],
                    Tags=tags
                )
            
            # 데이터베이스에 인스턴스 정보 저장
            instance_data = {
                'instance_id': instance_id,
                'name': next((tag['Value'] for tag in tags if tag['Key'] == 'Name'), '') if tags else '',
                'instance_type': instance_type,
                'state': instance['State']['Name']
            }
            self._sync_instance_to_db(instance_data)
            
            return {
                'success': True,
                'message': f'인스턴스 {instance_id}가 성공적으로 생성되었습니다.',
                'data': {
                    'instance_id': instance_id,
                    'instance_type': instance_type,
                    'state': instance['State']['Name']
                }
            }
        except Exception as e:
            logging.error(f"인스턴스 생성 중 오류: {str(e)}")
            return {
                'success': False,
                'message': f'인스턴스 생성 중 오류가 발생했습니다: {str(e)}',
                'error': str(e)
            }
    
    def terminate_instance(self, instance_id):
        """
        EC2 인스턴스를 종료합니다.
        
        Args:
            instance_id (str): 종료할 EC2 인스턴스의 ID
            
        Returns:
            dict: AWS API 응답
        """
        try:
            response = self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            # 데이터베이스 업데이트
            self._update_instance_state(instance_id, 'shutting-down')
            return {
                'success': True,
                'message': f'인스턴스 {instance_id} 종료 요청이 성공적으로 처리되었습니다.',
                'data': response
            }
        except Exception as e:
            logging.error(f"인스턴스 종료 중 오류: {str(e)}")
            return {
                'success': False,
                'message': f'인스턴스 종료 중 오류가 발생했습니다: {str(e)}',
                'error': str(e)
            }
    
    def reboot_instance(self, instance_id):
        """
        EC2 인스턴스를 재부팅합니다.
        
        Args:
            instance_id (str): 재부팅할 EC2 인스턴스의 ID
            
        Returns:
            dict: AWS API 응답
        """
        try:
            response = self.ec2_client.reboot_instances(InstanceIds=[instance_id])
            return {
                'success': True,
                'message': f'인스턴스 {instance_id} 재부팅 요청이 성공적으로 처리되었습니다.',
                'data': response
            }
        except Exception as e:
            logging.error(f"인스턴스 재부팅 중 오류: {str(e)}")
            return {
                'success': False,
                'message': f'인스턴스 재부팅 중 오류가 발생했습니다: {str(e)}',
                'error': str(e)
            }
    
    def manage_tags(self, instance_id, tags, action='create'):
        """
        EC2 인스턴스의 태그를 관리합니다.
        
        Args:
            instance_id (str): 태그를 관리할 EC2 인스턴스의 ID
            tags (list): 태그 목록 [{'Key': 'key1', 'Value': 'value1'}, ...]
            action (str): 'create' 또는 'delete'
            
        Returns:
            dict: AWS API 응답
        """
        try:
            if action == 'create':
                response = self.ec2_client.create_tags(
                    Resources=[instance_id],
                    Tags=tags
                )
                message = f'인스턴스 {instance_id}에 태그가 성공적으로 추가되었습니다.'
            elif action == 'delete':
                response = self.ec2_client.delete_tags(
                    Resources=[instance_id],
                    Tags=tags
                )
                message = f'인스턴스 {instance_id}에서 태그가 성공적으로 삭제되었습니다.'
            else:
                return {
                    'success': False,
                    'message': f'유효하지 않은 태그 작업입니다: {action}',
                    'error': 'Invalid action'
                }
                
            # 이름 태그가 있으면 데이터베이스 업데이트
            name_tag = next((tag['Value'] for tag in tags if tag['Key'] == 'Name'), None)
            if name_tag and action == 'create':
                self._update_instance_name(instance_id, name_tag)
                
            return {
                'success': True,
                'message': message,
                'data': response
            }
        except Exception as e:
            logging.error(f"태그 관리 중 오류: {str(e)}")
            return {
                'success': False,
                'message': f'태그 관리 중 오류가 발생했습니다: {str(e)}',
                'error': str(e)
            }
    
    def get_gpu_info(self, instance_id):
        """
        EC2 인스턴스의 GPU 정보를 조회합니다.
        
        Args:
            instance_id (str): GPU 정보를 조회할 EC2 인스턴스의 ID
            
        Returns:
            dict: GPU 정보
        """
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance_data = response['Reservations'][0]['Instances'][0]
            instance_type = instance_data['InstanceType']
            
            # 인스턴스 타입에 따른 GPU 정보 반환
            gpu_info = self._get_gpu_info_by_instance_type(instance_type)
            
            return {
                'success': True,
                'message': f'인스턴스 {instance_id}의 GPU 정보를 성공적으로 조회했습니다.',
                'data': {
                    'instance_id': instance_id,
                    'instance_type': instance_type,
                    'gpu_info': gpu_info
                }
            }
        except Exception as e:
            logging.error(f"GPU 정보 조회 중 오류: {str(e)}")
            return {
                'success': False,
                'message': f'GPU 정보 조회 중 오류가 발생했습니다: {str(e)}',
                'error': str(e)
            }
    
    def _get_gpu_info_by_instance_type(self, instance_type):
        """
        인스턴스 타입에 따른 GPU 정보를 반환합니다.
        
        Args:
            instance_type (str): EC2 인스턴스 타입
            
        Returns:
            dict: GPU 정보
        """
        # GPU 인스턴스 타입 매핑
        gpu_instances = {
            'p2.xlarge': {'gpu_model': 'NVIDIA K80', 'gpu_count': 1, 'gpu_memory': '12 GB'},
            'p2.8xlarge': {'gpu_model': 'NVIDIA K80', 'gpu_count': 8, 'gpu_memory': '12 GB'},
            'p2.16xlarge': {'gpu_model': 'NVIDIA K80', 'gpu_count': 16, 'gpu_memory': '12 GB'},
            'p3.2xlarge': {'gpu_model': 'NVIDIA V100', 'gpu_count': 1, 'gpu_memory': '16 GB'},
            'p3.8xlarge': {'gpu_model': 'NVIDIA V100', 'gpu_count': 4, 'gpu_memory': '16 GB'},
            'p3.16xlarge': {'gpu_model': 'NVIDIA V100', 'gpu_count': 8, 'gpu_memory': '16 GB'},
            'g3.4xlarge': {'gpu_model': 'NVIDIA M60', 'gpu_count': 1, 'gpu_memory': '8 GB'},
            'g3.8xlarge': {'gpu_model': 'NVIDIA M60', 'gpu_count': 2, 'gpu_memory': '8 GB'},
            'g3.16xlarge': {'gpu_model': 'NVIDIA M60', 'gpu_count': 4, 'gpu_memory': '8 GB'},
            'g4dn.xlarge': {'gpu_model': 'NVIDIA T4', 'gpu_count': 1, 'gpu_memory': '16 GB'},
            'g4dn.2xlarge': {'gpu_model': 'NVIDIA T4', 'gpu_count': 1, 'gpu_memory': '16 GB'},
            'g4dn.4xlarge': {'gpu_model': 'NVIDIA T4', 'gpu_count': 1, 'gpu_memory': '16 GB'},
            'g4dn.8xlarge': {'gpu_model': 'NVIDIA T4', 'gpu_count': 1, 'gpu_memory': '16 GB'},
            'g4dn.16xlarge': {'gpu_model': 'NVIDIA T4', 'gpu_count': 1, 'gpu_memory': '16 GB'},
            'g4dn.12xlarge': {'gpu_model': 'NVIDIA T4', 'gpu_count': 4, 'gpu_memory': '16 GB'},
            'g4dn.metal': {'gpu_model': 'NVIDIA T4', 'gpu_count': 8, 'gpu_memory': '16 GB'},
            'g5.xlarge': {'gpu_model': 'NVIDIA A10G', 'gpu_count': 1, 'gpu_memory': '24 GB'},
            'g5.2xlarge': {'gpu_model': 'NVIDIA A10G', 'gpu_count': 1, 'gpu_memory': '24 GB'},
            'g5.4xlarge': {'gpu_model': 'NVIDIA A10G', 'gpu_count': 1, 'gpu_memory': '24 GB'},
            'g5.8xlarge': {'gpu_model': 'NVIDIA A10G', 'gpu_count': 1, 'gpu_memory': '24 GB'},
            'g5.16xlarge': {'gpu_model': 'NVIDIA A10G', 'gpu_count': 1, 'gpu_memory': '24 GB'},
            'g5.12xlarge': {'gpu_model': 'NVIDIA A10G', 'gpu_count': 4, 'gpu_memory': '24 GB'},
            'g5.24xlarge': {'gpu_model': 'NVIDIA A10G', 'gpu_count': 4, 'gpu_memory': '24 GB'},
            'g5.48xlarge': {'gpu_model': 'NVIDIA A10G', 'gpu_count': 8, 'gpu_memory': '24 GB'}
        }
        
        if instance_type in gpu_instances:
            gpu_info = gpu_instances[instance_type]
            gpu_info['has_gpu'] = True
            return gpu_info
        else:
            return {'has_gpu': False, 'gpu_model': None, 'gpu_count': 0, 'gpu_memory': '0 GB'}
    
    def _sync_instance_to_db(self, instance_data):
        """
        EC2 인스턴스 정보를 데이터베이스에 동기화합니다.
        
        Args:
            instance_data (dict): 인스턴스 정보
        """
        try:
            with transaction.atomic():
                instance, created = Instance.objects.update_or_create(
                    instance_id=instance_data['instance_id'],
                    defaults={
                        'name': instance_data.get('name', ''),
                        'instance_type': instance_data.get('instance_type', ''),
                        'state': instance_data.get('state', '')
                    }
                )
                logging.info(f"{'생성됨' if created else '업데이트됨'}: {instance.instance_id}")
        except Exception as e:
            logging.error(f"데이터베이스 동기화 중 오류: {str(e)}")
    
    def _update_instance_state(self, instance_id, state):
        """
        EC2 인스턴스의 상태를 데이터베이스에 업데이트합니다.
        
        Args:
            instance_id (str): 인스턴스 ID
            state (str): 상태
        """
        try:
            instance = Instance.objects.filter(instance_id=instance_id).first()
            if instance:
                instance.state = state
                instance.save(update_fields=['state'])
                logging.info(f"인스턴스 상태 업데이트: {instance_id} -> {state}")
            else:
                logging.warning(f"인스턴스를 찾을 수 없음: {instance_id}")
        except Exception as e:
            logging.error(f"인스턴스 상태 업데이트 중 오류: {str(e)}")
    
    def _update_instance_name(self, instance_id, name):
        """
        EC2 인스턴스의 이름을 데이터베이스에 업데이트합니다.
        
        Args:
            instance_id (str): 인스턴스 ID
            name (str): 이름
        """
        try:
            instance = Instance.objects.filter(instance_id=instance_id).first()
            if instance:
                instance.name = name
                instance.save(update_fields=['name'])
                logging.info(f"인스턴스 이름 업데이트: {instance_id} -> {name}")
            else:
                logging.warning(f"인스턴스를 찾을 수 없음: {instance_id}")
        except Exception as e:
            logging.error(f"인스턴스 이름 업데이트 중 오류: {str(e)}")
            
    def _handle_auto_restart(self, instance_id):
        """
        인스턴스 자동 재시작 처리를 합니다.
        
        Args:
            instance_id (str): 인스턴스 ID
            
        Returns:
            dict: 자동 재시작 처리 결과
        """
        try:
            instance = Instance.objects.filter(instance_id=instance_id).first()
            if not instance:
                return {
                    'auto_restart_initiated': False,
                    'message': f'인스턴스를 찾을 수 없음: {instance_id}'
                }
                
            # 자동 재시작이 활성화되어 있는지 확인
            if not instance.auto_restart_enabled:
                return {
                    'auto_restart_initiated': False,
                    'message': f'인스턴스 {instance_id}의 자동 재시작이 비활성화되어 있습니다.'
                }
                
            # 재시작 시도 횟수 증가
            instance.restart_attempts += 1
            instance.last_restart_attempt = timezone.now()
            instance.save(update_fields=['restart_attempts', 'last_restart_attempt'])
            
            logging.info(f'인스턴스 {instance_id} 자동 재시작 예약. 시도 횟수: {instance.restart_attempts}')
            
            # 여기서 실제 재시작 로직을 구현할 수 있음 (예: 스케줄러를 통한 재시작 예약)
            
            return {
                'auto_restart_initiated': True,
                'restart_attempts': instance.restart_attempts,
                'last_attempt': instance.last_restart_attempt.isoformat() if instance.last_restart_attempt else None,
                'message': f'인스턴스 {instance_id} 자동 재시작이 예약되었습니다.'
            }
        except Exception as e:
            logging.error(f'자동 재시작 처리 중 오류: {str(e)}')
            return {
                'auto_restart_initiated': False,
                'message': f'자동 재시작 처리 중 오류가 발생했습니다: {str(e)}'
            }
    
    def _reset_restart_attempts(self, instance_id):
        """
        인스턴스의 재시작 시도 횟수를 초기화합니다.
        
        Args:
            instance_id (str): 인스턴스 ID
        """
        try:
            instance = Instance.objects.filter(instance_id=instance_id).first()
            if instance and instance.restart_attempts > 0:
                instance.restart_attempts = 0
                instance.save(update_fields=['restart_attempts'])
                logging.info(f'인스턴스 {instance_id} 재시작 시도 횟수 초기화')
        except Exception as e:
            logging.error(f'재시작 시도 횟수 초기화 중 오류: {str(e)}')
    
    def toggle_auto_restart(self, instance_id):
        """
        인스턴스의 자동 재시작 상태를 토글합니다.
        
        Args:
            instance_id (str): 인스턴스 ID
            
        Returns:
            dict: 토글 결과
        """
        try:
            instance = Instance.objects.filter(instance_id=instance_id).first()
            if not instance:
                return {
                    'success': False,
                    'message': f'인스턴스를 찾을 수 없음: {instance_id}'
                }
                
            instance.auto_restart_enabled = not instance.auto_restart_enabled
            instance.save(update_fields=['auto_restart_enabled'])
            
            status = '활성화' if instance.auto_restart_enabled else '비활성화'
            logging.info(f'인스턴스 {instance_id} 자동 재시작 {status}')
            
            return {
                'success': True,
                'auto_restart_enabled': instance.auto_restart_enabled,
                'message': f'인스턴스 {instance_id}의 자동 재시작이 {status}되었습니다.'
            }
        except Exception as e:
            logging.error(f'자동 재시작 토글 중 오류: {str(e)}')
            return {
                'success': False,
                'message': f'자동 재시작 토글 중 오류가 발생했습니다: {str(e)}'
            }
    
    def cancel_auto_restart(self, instance_id):
        """
        인스턴스의 자동 재시작을 취소합니다.
        
        Args:
            instance_id (str): 인스턴스 ID
            
        Returns:
            dict: 취소 결과
        """
        try:
            instance = Instance.objects.filter(instance_id=instance_id).first()
            if not instance:
                return {
                    'success': False,
                    'message': f'인스턴스를 찾을 수 없음: {instance_id}'
                }
                
            # 자동 재시작 비활성화 및 시도 횟수 초기화
            instance.auto_restart_enabled = False
            instance.restart_attempts = 0
            instance.save(update_fields=['auto_restart_enabled', 'restart_attempts'])
            
            logging.info(f'인스턴스 {instance_id} 자동 재시작 취소')
            
            return {
                'success': True,
                'message': f'인스턴스 {instance_id}의 자동 재시작이 취소되었습니다.'
            }
        except Exception as e:
            logging.error(f'자동 재시작 취소 중 오류: {str(e)}')
            return {
                'success': False,
                'message': f'자동 재시작 취소 중 오류가 발생했습니다: {str(e)}'
            }