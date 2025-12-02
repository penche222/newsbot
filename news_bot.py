import requests
import os
import sys
from bs4 import BeautifulSoup

# ==========================================
# 환경변수 확인
# ==========================================
print("--- [1단계] 환경변수 점검 ---")
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not TOKEN:
    print("❌ 에러: TELEGRAM_TOKEN이 설정되지 않았습니다. Secrets를 확인하세요.")
    sys.exit(1)
else:
    print(f"✅ 토큰 확인됨 (앞 5자리: {TOKEN[:5]}...)")

if not CHAT_ID:
    print("❌ 에러: CHAT_ID가 설정되지 않았습니다. Secrets를 확인하세요.")
    sys.exit(1)
else:
    print(f"✅ 채팅ID 확인됨 ({CHAT_ID})")


# ==========================================
# 텔레그램 권한 & 고정 메시지 확인
# ==========================================
print("\n--- [2단계] 텔레그램 연결 및 권한 점검 ---")
url_info = f"https://api.telegram.org/bot{TOKEN}/getChat?chat_id={CHAT_ID}"
res_info = requests.get(url_info)
info_json = res_info.json()

print(f"📡 응답 코드: {res_info.status_code}")
if res_info.status_code != 200:
    print(f"❌ 텔레그램 접속 실패! 응답 내용:\n{res_info.text}")
    print("👉 원인 1: CHAT_ID가 틀렸을 수 있습니다. (-100으로 시작하는지 확인)")
    print("👉 원인 2: 봇이 채널에 강퇴당했거나 초대되지 않았습니다.")
else:
    print("✅ 텔레그램 연결 성공!")
    # 고정 메시지 확인
    if "result" in info_json and "pinned_message" in info_json["result"]:
        pinned = info_json["result"]["pinned_message"]["text"]
        print(f"📌 고정 메시지 감지됨: '{pinned}'")
    else:
        print("⚠️ 고정 메시지가 없습니다. (권한은 정상입니다)")
        # 봇이 관리자가 아니면 고정 메시지를 못 읽을 수도 있음
        print("👉 참고: 봇이 '관리자(Admin)'가 아니면 고정 메시지를 못 읽을 수 있습니다.")


# ==========================================
# 테스트 메시지 전송 시도
# ==========================================
print("\n--- [3단계] 강제 메시지 전송 테스트 ---")
url_send = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": "🚀 테스트 메시지입니다. 이게 보이면 봇은 정상입니다.",
}
res_send = requests.post(url_send, json=payload)

if res_send.status_code == 200:
    print("✅ 테스트 메시지 전송 성공! 텔레그램을 확인하세요.")
else:
    print(f"❌ 메시지 전송 실패! (응답 코드: {res_send.status_code})")
    print(f"내용: {res_send.text}")


# ==========================================
# 네이버 뉴스 크롤링 테스트
# ==========================================
print("\n--- [4단계] 네이버 뉴스 크롤링 테스트 ---")
test_keyword = "삼성전자"
search_url = f"https://search.naver.com/search.naver?where=news&query={test_keyword}&sort=1"
headers = {"User-Agent": "Mozilla/5.0"}
res_news = requests.get(search_url, headers=headers)
soup = BeautifulSoup(res_news.text, 'html.parser')
items = soup.select(".news_tit")

print(f"검색어: {test_keyword}")
if len(items) > 0:
    print(f"✅ 크롤링 성공! 발견된 기사 수: {len(items)}개")
    print(f"첫 번째 기사 제목: {items[0].get_text()}")
else:
    print("❌ 크롤링 실패! 기사를 하나도 못 찾았습니다.")
    print("👉 원인: 네이버 HTML 구조가 바뀌었거나, 차단당했을 수 있습니다.")

print("\n--- [진단 종료] ---")
