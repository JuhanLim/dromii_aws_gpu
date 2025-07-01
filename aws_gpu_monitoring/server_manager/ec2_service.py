import boto3
from django.conf import settings

class EC2Service:
    def __init__(self):
        self.ec2 = boto3.client('ec2', 
                               aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                               aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                               region_name=settings.AWS_DEFAULT_REGION)
    
    def start_instance(self, instance_id):
        response = self.ec2.start_instances(InstanceIds=[instance_id])
        return response
    
    def stop_instance(self, instance_id):
        response = self.ec2.stop_instances(InstanceIds=[instance_id])
        return response
    
    def get_instance_status(self, instance_id):
        response = self.ec2.describe_instances(InstanceIds=[instance_id])
        return response['Reservations'][0]['Instances'][0]['State']['Name']