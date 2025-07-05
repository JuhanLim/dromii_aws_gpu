#!/bin/bash

# 컨테이너 이름 설정
CONTAINER_NAME=dromii_aws_gpu

# 컨테이너 ID 가져오기
CONTAINER_ID=$(docker ps -qf "name=$CONTAINER_NAME")

# 컨테이너가 실행 중인지 확인
if [ -z "$CONTAINER_ID" ]; then
  echo "❌ 컨테이너 '$CONTAINER_NAME'를 찾을 수 없습니다."
  exit 1
fi

echo "✅ 컨테이너 '$CONTAINER_NAME' (ID: $CONTAINER_ID) 확인됨"

# 기존 Gunicorn 프로세스 종료
echo "🛑 기존 Gunicorn 프로세스 종료 중..."
docker exec -it $CONTAINER_ID pkill gunicorn

# Gunicorn 로그 디렉토리 생성 (필요 시)
#LOG_DIR=/app/aws_gpu_monitoring/aws_gpu_monitoring/log
#docker exec -it $CONTAINER_ID mkdir -p $LOG_DIR

# 새로운 Gunicorn 프로세스 시작
echo "🚀 새로운 Gunicorn 프로세스 시작 중..."
docker exec -d $CONTAINER_ID /app/venv_awsgpu/bin/gunicorn \
  aws_gpu_monitoring.wsgi:application \
  --bind unix:/app/aws_gpu_monitoring/gunicorn.sock \
  --workers 3 \
  --chdir /app/aws_gpu_monitoring \
  --log-file /app/aws_gpu_monitoring/logs/gunicorn_error.log

echo "✅ Gunicorn 재시작 완료"