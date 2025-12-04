#!/bin/bash

# Rasa + ngrok 자동 시작 스크립트

# 가상환경 활성화
source .venv/bin/activate

# 기존 프로세스 종료
echo "기존 프로세스 종료 중..."
pkill -f "rasa run" 2>/dev/null
pkill -f "ngrok" 2>/dev/null
sleep 2

# ngrok 설치 확인
if ! command -v ngrok &> /dev/null; then
    echo "ngrok이 설치되어 있지 않습니다. 설치 중..."
    curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
      sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
      echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
      sudo tee /etc/apt/sources.list.d/ngrok.list && \
      sudo apt update && sudo apt install ngrok

    echo ""
    echo "ngrok 설치가 완료되었습니다."
    echo "ngrok authtoken을 설정해주세요:"
    echo "  ngrok config add-authtoken <YOUR_AUTHTOKEN>"
    echo ""
    read -p "authtoken을 입력하세요 (Enter를 누르면 건너뜁니다): " token
    if [ ! -z "$token" ]; then
        ngrok config add-authtoken "$token"
    fi
fi

echo ""
echo "========================================"
echo "Rasa 서버 시작 중..."
echo "========================================"
echo ""

# Actions 서버 시작
echo "1. Actions 서버 시작 (포트 5055)..."
nohup rasa run actions --port 5055 > actions.log 2>&1 &
ACTIONS_PID=$!
sleep 5

# Rasa 서버 시작
echo "2. Rasa 서버 시작 (포트 5005)..."
nohup rasa run --enable-api --cors "*" --port 5005 > rasa.log 2>&1 &
RASA_PID=$!
sleep 5

# ngrok 터널 시작
echo "3. ngrok 터널 시작..."
nohup ngrok http 5005 > ngrok.log 2>&1 &
NGROK_PID=$!
sleep 3

echo ""
echo "========================================"
echo "모든 서버가 시작되었습니다!"
echo "========================================"
echo ""
echo "로컬 주소:"
echo "  - Rasa Server: http://localhost:5005"
echo "  - Actions Server: http://localhost:5055"
echo ""
echo "프로세스 ID:"
echo "  - Rasa Server PID: $RASA_PID"
echo "  - Actions Server PID: $ACTIONS_PID"
echo "  - ngrok PID: $NGROK_PID"
echo ""

# ngrok URL 확인
sleep 2
echo "ngrok 공개 URL:"
curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"[^"]*' | grep -o 'https://[^"]*' || echo "  ngrok URL을 가져오는 중..."

echo ""
echo "========================================"
echo ""
echo "로그 파일:"
echo "  - Rasa: rasa.log"
echo "  - Actions: actions.log"
echo "  - ngrok: ngrok.log"
echo ""
echo "ngrok 대시보드: http://localhost:4040"
echo ""
echo "모든 서버를 중지하려면:"
echo "  pkill -f 'rasa run' && pkill -f 'ngrok'"
echo ""
echo "========================================"
