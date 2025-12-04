#!/bin/bash

# Rasa 자동 시작 스크립트

# 가상환경 활성화
source .venv/bin/activate

# 기존 Rasa 프로세스 종료 (있다면)
pkill -f "rasa run" 2>/dev/null
pkill -f "rasa run actions" 2>/dev/null

echo "Starting Rasa Actions Server on port 5055..."
rasa run actions --port 5055 &
ACTIONS_PID=$!

# Actions 서버가 시작될 때까지 대기
sleep 5

echo "Starting Rasa Server on port 5005..."
rasa run --enable-api --cors "*" --port 5005 &
RASA_PID=$!

echo ""
echo "========================================"
echo "Rasa 서버가 시작되었습니다!"
echo "========================================"
echo "Rasa Server: http://localhost:5005"
echo "Actions Server: http://localhost:5055"
echo ""
echo "Rasa Server PID: $RASA_PID"
echo "Actions Server PID: $ACTIONS_PID"
echo ""
echo "서버를 중지하려면: pkill -f 'rasa run'"
echo "========================================"

# 프로세스 유지 (포그라운드에서 실행하려면 주석 해제)
# wait
