import requests
import datetime
import os
import urllib.parse
import xml.etree.ElementTree as ET # 파이썬 기본 내장 (설치 불필요)

# ==========================================
# 1. 설정 (GitHub Secrets에서 가져옴)
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ==========================================
# 2. 기능 함수들
# ==========================================
def send_telegram_message(text):
    """텔레그램으로 메시지를 보냅니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"전송 실패: {e}")

def get_keywords():
    """텔레그램 고정 메시지에서 키워드를 읽어옵니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat?chat_id={CHAT_ID}"
    default_keyword = ["삼성전자"]
    
    try:
        res = requests.get(url).json()
        if "result" in res and "pinned_message" in res["result"]:
            text = res["result"]["pinned_message"]["text"]
            if text.startswith("설정:"):
                keywords = [k.strip() for k in text.replace("설정:", "").split(",") if k.strip()]
                return keywords, True
    except Exception as e:
        print(f"고정 메시지 확인 에러: {e}")
        
    return default_keyword, False

def get_google_news(keyword):
    """구글 뉴스 RSS 검색 (기본 라이브러리 사용 - 에러 없음)"""
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        res = requests.get(url)
        # XML 파싱 (BeautifulSoup 대신 가볍고 튼튼한 ElementTree 사용)
        root = ET.fromstring(res.content)
        
        # 뉴스 아이템들 찾기
        items = root.findall(".//item")
        
        if not items:
            return None

        result_text = f"\n🔍 <b>[{keyword}]</b>\n"
        
        count = 0
        for item in items:
            if count >= 3: break # 3개까지만
            
            # 제목과 링크 추출
            title = item.find("title").text
            link = item.find("link").text
            
            result_text += f"- <a href='{link}'>{title}</a>\n"
            count += 1
            
        return result_text

    except Exception as e:
        print(f"크롤링 에러 ({keyword}): {e}")
        return None

# ==========================================
# 3. 메인 실행
# ==========================================
if __name__ == "__main__":
    print("뉴스 봇 실행 시작...")
    
    # 환경변수 체크 (토큰 없으면 에러 로그 출력 후 종료)
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ 에러: Secrets 설정이 안 되어 있습니다.")
        exit(1)

    keywords, is_custom = get_keywords()
    
    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    final_message = f"📰 <b>뉴스 브리핑 ({today})</b>\n"
    
    has_news = False
    for kw in keywords:
        news_content = get_google_news(kw)
        if news_content:
            final_message += news_content
            has_news = True
            
    if has_news:
        send_telegram_message(final_message)
        print("✅ 전송 완료")
    else:
        send_telegram_message(f"오늘은 '{', '.join(keywords)}' 관련 뉴스가 없습니다.")
        print("✅ 뉴스 없음 (정상 종료)")
