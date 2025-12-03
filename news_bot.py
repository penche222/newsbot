import requests
import datetime
import os
import urllib.parse
import xml.etree.ElementTree as ET
import time # 시간 지연을 위해 추가

# ==========================================
# 1. 설정
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ==========================================
# 2. 날짜 계산 (어제 날짜 구하기)
# ==========================================
def get_yesterday_range():
    # UTC + 9시간 = 한국 시간
    now_kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    yesterday = now_kst - datetime.timedelta(days=1)
    return yesterday.date()

# ==========================================
# 3. 기능 함수들
# ==========================================
def send_telegram_message(text):
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
    """고정 메시지 읽기 (콤마, 줄바꿈 모두 지원)"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat?chat_id={CHAT_ID}"
    default_keyword = ["삼성전자"]
    
    try:
        res = requests.get(url).json()
        if "result" in res and "pinned_message" in res["result"]:
            text = res["result"]["pinned_message"]["text"]
            
            # '설정' 키워드 확인
            if "설정" in text:
                # '설정' 글자 제거 및 콜론 제거
                clean_text = text.replace("설정", "").replace(":", "")
                
                # 줄바꿈(\n)을 콤마(,)로 바꾼 뒤 쪼개기 (엔터로 쳐도 인식되게)
                clean_text = clean_text.replace("\n", ",")
                
                # 콤마로 나누고 공백 제거
                keywords = [k.strip() for k in clean_text.split(",") if k.strip()]
                return keywords, True
    except:
        pass
    return default_keyword, False

def get_google_news_yesterday(keyword):
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={encoded_keyword}+when:2d&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        res = requests.get(url)
        root = ET.fromstring(res.content)
        items = root.findall(".//item")
        
        if not items: return None

        target_date = get_yesterday_range()
        filtered_items = []

        for item in items:
            # 날짜 필터링 로직 (생략 시 최신 뉴스 모두 가져옴)
            # 여기서는 어제 뉴스만 가져오도록 유지
            try:
                from email.utils import parsedate_to_datetime
                pub_date_str = item.find("pubDate").text
                article_dt_utc = parsedate_to_datetime(pub_date_str)
                article_dt_kst = article_dt_utc + datetime.timedelta(hours=9)
                
                if article_dt_kst.date() == target_date:
                    filtered_items.append(item)
            except:
                continue

        if not filtered_items:
            return None

        # 종목별 개별 메시지 생성
        result_text = f"🔍 <b>[{keyword}]</b>\n"
        
        count = 0
        for item in filtered_items:
            if count >= 3: break
            title = item.find("title").text
            link = item.find("link").text
            result_text += f"- <a href='{link}'>{title}</a>\n"
            count += 1
            
        return result_text

    except Exception as e:
        print(f"에러 ({keyword}): {e}")
        return None

# ==========================================
# 4. 메인 실행
# ==========================================
if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID:
        exit(1)

    keywords, is_custom = get_keywords()
    yesterday_str = get_yesterday_range().strftime("%Y-%m-%d")
    
    # 1. 시작 알림 (한 번만 보냄)
    intro_msg = f"📰 <b>News Briefing ({yesterday_str})</b>\n"
    intro_msg += f"총 {len(keywords)}개 종목의 뉴스를 검색합니다."
    send_telegram_message(intro_msg)
    
    # 2. 종목별로 루프 돌면서 개별 전송
    count_news = 0
    for kw in keywords:
        news_content = get_google_news_yesterday(kw)
        
        if news_content:
            send_telegram_message(news_content) # ★ 핵심: 종목마다 바로바로 보냄
            count_news += 1
            time.sleep(1) # ★ 핵심: 텔레그램 도배 방지를 위해 1초 휴식
            
    # 3. 마무리
    if count_news == 0:
        send_telegram_message(f"오늘은 설정된 종목의 어제 자 뉴스가 하나도 없습니다.")
    else:
        print("전송 완료")
