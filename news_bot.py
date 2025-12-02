import requests
from bs4 import BeautifulSoup
import datetime
import os

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
        "disable_web_page_preview": True # 링크 미리보기 끄기 (깔끔하게)
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"전송 실패: {e}")

def get_keywords():
    """텔레그램 고정 메시지에서 키워드를 읽어옵니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat?chat_id={CHAT_ID}"
    default_keyword = ["특징주"] # 기본값
    
    try:
        res = requests.get(url).json()
        if "result" in res and "pinned_message" in res["result"]:
            text = res["result"]["pinned_message"]["text"]
            if text.startswith("설정:"):
                # "설정: 삼성전자, SK하이닉스" -> ["삼성전자", "SK하이닉스"]
                keywords = [k.strip() for k in text.replace("설정:", "").split(",") if k.strip()]
                return keywords, True # 성공
    except Exception as e:
        print(f"고정 메시지 확인 에러: {e}")
        
    return default_keyword, False # 실패 시 기본값 반환

def get_naver_news(keyword):
    """네이버 뉴스 검색 (최신순)"""
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sort=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        news_list = soup.select(".news_tit")
        
        if not news_list:
            return None

        # 결과 텍스트 만들기
        result_text = f"\n🔍 <b>[{keyword}]</b>\n"
        for i, item in enumerate(news_list):
            if i >= 3: break # 3개까지만
            title = item.get_text().replace("<", "").replace(">", "") # 태그 깨짐 방지
            link = item['href']
            result_text += f"- <a href='{link}'>{title}</a>\n"
            
        return result_text
    except Exception as e:
        print(f"크롤링 에러 ({keyword}): {e}")
        return None

# ==========================================
# 3. 메인 실행
# ==========================================
if __name__ == "__main__":
    print("뉴스 봇 실행 시작...")
    
    # 1. 키워드 가져오기
    keywords, is_custom = get_keywords()
    
    # 2. 날짜 헤더 만들기
    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    final_message = f"📰 <b>뉴스 브리핑 ({today})</b>\n"
    
    if not is_custom:
        final_message += "(💡 팁: 채널에 '설정: 종목명'을 적고 고정하면 해당 종목을 검색합니다)\n"

    # 3. 뉴스 긁어오기
    has_news = False
    for kw in keywords:
        news_content = get_naver_news(kw)
        if news_content:
            final_message += news_content
            has_news = True
            
    # 4. 전송
    if has_news:
        send_telegram_message(final_message)
        print("전송 완료")
    else:
        send_telegram_message(f"오늘은 '{', '.join(keywords)}' 관련 뉴스가 없습니다.")
        print("뉴스 없음")
