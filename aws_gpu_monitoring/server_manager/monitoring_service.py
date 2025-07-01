import boto3
from datetime import datetime, timedelta

class CloudWatchService:
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')
    
    def get_cpu_utilization(self, instance_id, start_time, end_time):
        response = self.cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Average']
        )
        return response['Datapoints']