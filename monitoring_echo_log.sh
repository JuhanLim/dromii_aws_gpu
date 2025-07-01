#!/bin/bash
export PATH=$PATH:/usr/bin:/usr/local/bin:/usr/local/nvidia/bin

# 로그 파일 경로 설정
LOG_DIR="/home/juhan/log/server_metrics"
LOG_FILE="$LOG_DIR/metrics.log"
CURRENT_YEAR_MONTH=$(date +"%Y-%m")
CURRENT_DATE=$(date +"%Y-%m-%d")
DAILY_REPORT="$LOG_DIR/daily/daily_report_$CURRENT_DATE.txt"
MONTHLY_REPORT="$LOG_DIR/monthly/monthly_report_$CURRENT_YEAR_MONTH.txt"
STATUS_LOG="$LOG_DIR/status.log"

# 로그 디렉토리 생성
[ ! -d "$LOG_DIR" ] && mkdir -p "$LOG_DIR"

# 현재 시간 기록
TIMESTAMP=$(date +%s)
DATE=$(date +"%Y-%m-%d %H:%M:%S")

# 사용자 목록
USERS=("hayeong" "chaeyoung" "juhan" "jinhyeong")

# 디스크 사용량 로깅
MOUNTPOINT1="/dev/xvda1"
USAGES=$(df -m | grep "$MOUNTPOINT1")
[ -n "$USAGES" ] && {
    totalSize=$(echo $USAGES | awk '{print $2}')
    usedSize=$(echo $USAGES | awk '{print $3}')
    availSize=$(echo $USAGES | awk '{print $4}')
} || echo "Mount point '$MOUNTPOINT1' not found at $DATE" >> "$LOG_FILE"

MOUNTPOINT2="/dev/xvdb"
USAGES=$(df -m | grep "$MOUNTPOINT2")
[ -n "$USAGES" ] && {
    usedSize_xvdb=$(echo $USAGES | awk '{print $3}')
    availSize_xvdb=$(echo $USAGES | awk '{print $4}')
} || echo "Mount point '$MOUNTPOINT2' not found at $DATE" >> "$LOG_FILE"

# 사용자별 디스크 사용량
for user in "${USERS[@]}"; do
    user_disk_usage=$(du -sm /mnt/home/$user | awk '{print $1}')
    echo "User $user Disk Usage: $user_disk_usage MB" >> "$LOG_FILE"
    user_disk2_usage=$(du -sm /mnt/$user | awk '{print $1}')
    echo "User $user Disk2 Usage: $user_disk2_usage MB" >> "$LOG_FILE"
done

# CPU 사용량 (전체 합계 계산)
total_cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2 + $4}')
echo "Total CPU Usage: ${total_cpu_usage}%" >> "$LOG_FILE"

# CPU 사용량 (사용자별 집계)
echo "CPU Usage by User:" >> "$LOG_FILE"
ps -eo ruser,%cpu --no-headers | awk -v users="${USERS[*]}" '
    BEGIN { split(users, userlist, " "); for (i in userlist) sum[userlist[i]] = 0 }
    $1 in sum { sum[$1] += $2 }
    END { for (u in sum) printf "User %s CPU Usage: %.2f%%\n", u, sum[u] }
' >> "$LOG_FILE"

# GPU 사용량 및 프로세스
if command -v nvidia-smi > /dev/null 2>&1; then
    gpu0_usage=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits -i 0)
    gpu0_usage_mib=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0)
    gpu0_temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits -i 0)
    gpu1_usage=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits -i 1)
    gpu1_usage_mib=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1)
    gpu1_temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits -i 1)
    
    gpu_processes=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits | sort -nr -k3 | head -n5)
    if [[ -z "$gpu_processes" ]]; then
        echo "No GPU processes running" >> "$LOG_FILE"
    else
        echo "Top 5 GPU Processes (Name, Memory):" >> "$LOG_FILE"
        echo "$gpu_processes" | awk -F', ' '{printf "%-30s %s MiB\n", $2, $3}' >> "$LOG_FILE"
    fi
fi

# CSV 로그 기록
echo "$TIMESTAMP,$DATE,$totalSize,$usedSize,$availSize,$usedSize_xvdb,$availSize_xvdb,$total_cpu_usage,$gpu0_usage,$gpu0_usage_mib,$gpu0_temp,$gpu1_usage,$gpu1_usage_mib,$gpu1_temp" >> "$LOG_FILE"

# 통계 계산 및 보고서 생성 함수
calculate_stats() {
    local period=$1
    local output_file=$2
    local cutoff=$3
    local temp_file="/tmp/metrics_temp_$$.csv"
    local temp_cpu="/tmp/cpu_temp_$$.txt"
    local temp_gpu="/tmp/gpu_temp_$$.txt"

    # 기간 내 데이터 필터링
    awk -F',' -v cutoff="$cutoff" '$1 >= cutoff' "$LOG_FILE" > "$temp_file"

    if [ -s "$temp_file" ]; then
        echo "=== $period Report ($DATE) ===" > "$output_file"
        [ "$period" = "Daily" ] && echo "Period: $CURRENT_DATE" >> "$output_file" || echo "Period: $CURRENT_YEAR_MONTH" >> "$output_file"
        echo "" >> "$output_file"

        # 사용자별 디스크 사용량 평균
        for user in "${USERS[@]}"; do
            avg=$(grep "User $user Disk Usage" "$LOG_FILE" | awk '{sum+=$5; count++} END {if(count>0) printf "%.2f", sum/count}')
            [ -n "$avg" ] && echo "Disk /mnt/home/$user Used Avg: $avg MB" >> "$output_file"
            avg2=$(grep "User $user Disk2 Usage" "$LOG_FILE" | awk '{sum+=$5; count++} END {if(count>0) printf "%.2f", sum/count}')
            [ -n "$avg2" ] && echo "Disk2 /mnt/$user Used Avg: $avg2 MB" >> "$output_file"
        done

        # 기본 디스크 통계
        awk -F',' '
        NR>0 {total_xvda1+=$4; avail_xvda1+=$5; total_xvdb+=$6; avail_xvdb+=$7; cpu+=$8; gpu0+=$9; gpu0_mib+=$10; gpu0_temp+=$11; gpu1+=$12; gpu1_mib+=$13; gpu1_temp+=$14; count++}
        END {
            printf "Disk /dev/xvda1 Used Avg: %.2f MB\n", total_xvda1/count
            printf "Disk /dev/xvda1 Avail Avg: %.2f MB\n", avail_xvda1/count
            printf "Disk /dev/xvdb Used Avg: %.2f MB\n", total_xvdb/count
            printf "Disk /dev/xvdb Avail Avg: %.2f MB\n", avail_xvdb/count
            printf "CPU Usage Avg: %.2f%%\n", cpu/count
            printf "GPU0 Usage Avg: %.2f%%\n", gpu0/count
            printf "GPU0 Memory Usage Avg: %.2f MiB\n", gpu0_mib/count
            printf "GPU0 Temperature Avg: %.2f °C\n", gpu0_temp/count
            printf "GPU1 Usage Avg: %.2f%%\n", gpu1/count
            printf "GPU1 Memory Usage Avg: %.2f MiB\n", gpu1_mib/count
            printf "GPU1 Temperature Avg: %.2f °C\n", gpu1_temp/count
        }' "$temp_file" >> "$output_file"

        # CPU 사용자별 집계
        grep "User .* CPU Usage" "$LOG_FILE" | awk -F'User | CPU Usage: ' '{print $2, $3}' | tr -d '%' > "$temp_cpu"
        awk '{sum[$1]+=$2; count[$1]++} END {for(u in sum) printf "CPU Usage Avg %s: %.2f%%\n", u, sum[u]/count[u]}' "$temp_cpu" | sort -k4 -nr >> "$output_file"

        # GPU 프로세스 집계
        grep -A5 "Top 5 GPU Processes" "$LOG_FILE" | grep -vE "Top 5 GPU Processes|No GPU processes running" | grep -v "\-\-" | grep -v "^$" > "$temp_gpu"
        if [ -s "$temp_gpu" ]; then
            awk '{proc[$1]+=$2; mem[$1]+=$3; count[$1]++} END {for(p in proc) printf "GPU Memory Usage Avg Process Name %s: %.2f%% (%.2f MiB)\n", p, proc[p]/count[p], mem[p]/count[p]}' "$temp_gpu" >> "$output_file"
        else
            echo "No GPU processes detected during this period" >> "$output_file"
        fi
    else
        echo "No data available for $period report at $DATE" > "$output_file"
    fi

    rm -f "$temp_file" "$temp_cpu" "$temp_gpu"
}

# 1일 및 30일 통계 계산
DAY_START=$(date -d "$CURRENT_DATE 00:00:00" +%s)
MONTH_START=$(date -d "$CURRENT_YEAR_MONTH-01 00:00:00" +%s)
calculate_stats "Daily" "$DAILY_REPORT" "$DAY_START"
calculate_stats "Monthly" "$MONTHLY_REPORT" "$MONTH_START"

# 상태 기록
{
    echo "=== Current Status ($DATE) ==="
    echo "Disk /dev/xvda1 - Total: $totalSize MB, Used: $usedSize MB, Avail: $availSize MB"
    echo "Disk /dev/xvdb - Used: $usedSize_xvdb MB, Avail: $availSize_xvdb MB"
    echo "CPU Usage by User:"
    grep "User .* CPU Usage" "$LOG_FILE" | sed -n '$!b;p'  # 마지막 기록만 출력
    echo "GPU0 Usage: $gpu0_usage%, Memory: $gpu0_usage_mib MiB, Temperature: $gpu0_temp °C"
    echo "GPU1 Usage: $gpu1_usage%, Memory: $gpu1_usage_mib MiB, Temperature: $gpu1_temp °C"
} > "$STATUS_LOG"