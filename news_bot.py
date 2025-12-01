import requests
from bs4 import BeautifulSoup
import datetime
import os
import sys

# ==========================================
# 1. 설정 구간 (GitHub Secrets 이용)
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ==========================================
# 2. 텔레그램 기능 함수들
# ==========================================
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"전송 실패: {e}")

def get_keywords_from_pinned_message():
    """
    텔레그램 채널의 '고정 메시지'를 읽어서 검색어 리스트로 변환합니다.
    형식 예시: "설정: 삼성전자, SK하이닉스, 특징주"
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat?chat_id={CHAT_ID}"
    
    try:
        response = requests.get(url).json()
        
        # 고정된 메시지가 있는지 확인
        if "result" in response and "pinned_message" in response["result"]:
            pinned_text = response["result"]["pinned_message"]["text"]
            
            # "설정:" 이라는 단어로 시작하는지 확인 (오작동 방지)
            if pinned_text.startswith("설정:"):
                # "설정:" 뒤의 글자를 가져와서 콤마(,)로 나눔
                keywords_str = pinned_text.replace("설정:", "")
                # 콤마로 나누고 앞뒤 공백 제거
                keywords_list = [k.strip() for k in keywords_str.split(",") if k.strip()]
                
                print(f"텔레그램에서 불러온 키워드: {keywords_list}")
                return keywords_list
            
        print("고정 메시지에서 '설정:' 키워드를 찾지 못했습니다. 기본값 사용.")
        return ["특징주"] # 고정 메시지가 없을 때 쓸 기본값

    except Exception as e:
        print(f"키워드 불러오기 실패: {e}")
        return ["특징주"] # 에러 발생 시 기본값

# ==========================================
# 3. 네이버 뉴스 크롤링 함수
# ==========================================
def get_news(keyword):
    # 정확도순(sort=1) 대신 최신순(sort=1) 사용 권장, 필요시 조정
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sort=1"
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        news_items = soup.select(".news_tit")
        
        if not news_items:
            return None

        message = f"\n🔍 <b>[{keyword}] 뉴스</b>\n"
        count = 0
        for item in news_items:
            if count >= 3: break # 3개만
            title = item.get_text()
            link = item['href']
            message += f"- <a href='{link}'>{title}</a>\n"
            count += 1
        return message

    except Exception as e:
        return f"[{keyword}] 크롤링 중 에러 발생: {e}"

# ==========================================
# 4. 메인 실행부
# ==========================================
if __name__ == "__main__":
    # 1. 텔레그램 고정 메시지에서 키워드 가져오기
    KEYWORDS = get_keywords_from_pinned_message()
    
    if not KEYWORDS:
        print("검색할 키워드가 없습니다.")
        sys.exit()

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    full_message = f"📢 <b>{today} 모닝 브리핑</b>\n(설정된 키워드: {', '.join(KEYWORDS)})\n"
    
    # 2. 뉴스 수집
    has_news = False
    for keyword in KEYWORDS:
        news_report = get_news(keyword)
        if news_report:
            full_message += news_report
            has_news = True
    
    # 3. 결과 전송 (뉴스가 하나라도 있을 때만)
    if has_news:
        send_telegram_message(full_message)
    else:
        print("전송할 새로운 뉴스가 없습니다.")
