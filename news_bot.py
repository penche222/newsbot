import requests
import os
import sys

# ==========================================
# 1. 환경변수(Secrets) 상태 점검
# ==========================================
print("--- [1단계] Secrets 값 점검 ---")
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# 1-1. 토큰 점검
if not TOKEN:
    print("❌ [치명적 오류] TELEGRAM_TOKEN이 없습니다! Secrets에 저장이 안 됐습니다.")
    sys.exit(1)
else:
    # 토큰 앞뒤에 공백이 있는지 확인
    if len(TOKEN) != len(TOKEN.strip()):
        print(f"❌ [원인 발견] 토큰에 불필요한 공백이 포함되어 있습니다. (길이: {len(TOKEN)})")
        print("👉 해결책: Secrets를 수정해서 앞뒤 공백을 지우세요.")
    else:
        print(f"✅ 토큰 형식 정상 (앞 5자리: {TOKEN[:5]}...)")

# 1-2. 채팅 ID 점검
if not CHAT_ID:
    print("❌ [치명적 오류] CHAT_ID가 없습니다! Secrets에 저장이 안 됐습니다.")
    sys.exit(1)
else:
    if len(CHAT_ID) != len(CHAT_ID.strip()):
        print(f"❌ [원인 발견] CHAT_ID에 불필요한 공백이 포함되어 있습니다.")
        print("👉 해결책: Secrets를 수정해서 앞뒤 공백을 지우세요.")
    else:
        print(f"✅ 채팅 ID 형식 정상 ({CHAT_ID})")


# ==========================================
# 2. 텔레그램 서버 접속 테스트 (getMe)
# ==========================================
print("\n--- [2단계] 봇 자체 테스트 (getMe) ---")
url_me = f"https://api.telegram.org/bot{TOKEN}/getMe"
res_me = requests.get(url_me)

if res_me.status_code == 200:
    bot_info = res_me.json()
    print(f"✅ 봇 로그인 성공! (봇 이름: {bot_info['result']['first_name']})")
else:
    print(f"❌ [원인 발견] 봇 토큰이 틀렸습니다. (응답 코드: {res_me.status_code})")
    print(f"👉 텔레그램 서버 응답: {res_me.text}")
    print("👉 해결책: 봇파더에게 토큰을 다시 받거나, Secrets에 오타 없이 복사했는지 확인하세요.")
    sys.exit(1)


# ==========================================
# 3. 메시지 전송 테스트 (sendMessage)
# ==========================================
print("\n--- [3단계] 메시지 전송 테스트 ---")
url_send = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": "🚨 진단 메시지입니다. 이게 보이면 ID는 맞습니다."
}

res_send = requests.post(url_send, json=payload)
print(f"📡 전송 시도 결과 코드: {res_send.status_code}")

if res_send.status_code == 200:
    print("🎉 성공! 텔레그램 메시지가 도착했을 겁니다.")
    print("👉 만약 이게 왔다면, 문제는 '뉴스 검색' 쪽에 있었던 겁니다.")
else:
    print("❌ [원인 발견] 메시지 전송 실패!")
    print(f"👉 텔레그램 에러 내용: {res_send.text}")
    
    # 에러 메시지별 친절한 해석
    err_text = res_send.text
    if "chat not found" in err_text:
        print("\n💡 [해석] '채널을 못 찾겠다'고 합니다.")
        print("1. CHAT_ID가 틀렸습니다. (현재 입력값: " + CHAT_ID + ")")
        print("2. ID 앞에 '-100'을 빼먹었는지 확인하세요.")
    elif "Unauthorized" in err_text:
        print("\n💡 [해석] 토큰이 틀렸습니다.")
    elif "bot is not a member" in err_text:
        print("\n💡 [해석] 봇이 채널에 없습니다.")
        print("👉 봇을 채널 관리자로 다시 초대하세요.")
    elif "Forbidden" in err_text:
        print("\n💡 [해석] 봇이 강퇴당했거나 권한이 없습니다.")

print("\n--- 진단 종료 ---")
