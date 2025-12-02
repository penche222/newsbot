import requests
import datetime
import os
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime # 날짜 해석용 도구

# ==========================================
# 1. 설정
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ==========================================
# 2. 날짜 계산 함수 (한국 시간 기준)
# ==========================================
def get_yesterday_range():
    """한국 시간 기준으로 '어제' 날짜를 구합니다."""
    # 현재 UTC 시간 + 9시간 = 한국 시간
    now_kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    yesterday = now_kst - datetime.timedelta(days=1)
    return yesterday.date() # 2025-12-01 형식으로 반환

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
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat?chat_id={CHAT_ID}"
    default_keyword = ["삼성전자"]
    
    try:
        res = requests.get(url).json()
        if "result" in res and "pinned_message" in res["result"]:
            text = res["result"]["pinned_message"]["text"]
            if "설정" in text:
                if ":" in text:
                    target = text.split(":", 1)[1]
                else:
                    target = text.replace("설정", "")
                return [k.strip() for k in target.split(",") if k.strip()], True
    except:
        pass
    return default_keyword, False

def get_google_news_yesterday(keyword):
    encoded_keyword = urllib.parse.quote(keyword)
    # when:2d를 붙여서 넉넉하게 최근 2일치 기사를 긁어옵니다.
    url = f"https://news.google.com/rss/search?q={encoded_keyword}+when:2d&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        res = requests.get(url)
        root = ET.fromstring(res.content)
        items = root.findall(".//item")
        
        if not items: return None

        target_date = get_yesterday_range() # 어제 날짜 (예: 12월 1일)
        filtered_items = []

        for item in items:
            pub_date_str = item.find("pubDate").text
            # RSS 날짜(영어)를 파이썬 날짜로 변환
            article_dt_utc = parsedate_to_datetime(pub_date_str)
            # 한국 시간으로 변환 (UTC+9)
            article_dt_kst = article_dt_utc + datetime.timedelta(hours=9)
            
            # 기사 날짜가 '어제'랑 똑같은지 확인
            if article_dt_kst.date() == target_date:
                filtered_items.append(item)

        if not filtered_items:
            return None

        result_text = f"\n🗓 <b>[{keyword}] 어제 뉴스 ({target_date})</b>\n"
        
        count = 0
        for item in filtered_items:
            if count >= 3: break # 어제 뉴스 중 상위 3개만
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
    
    # 한국 시간 기준 어제 날짜 표시
    yesterday_str = get_yesterday_range().strftime("%Y년 %m월 %d일")
    
    final_message = f"📰 <b>News Recap ({yesterday_str})</b>\n"
    final_message += "어제 하루 동안 발생한 주요 뉴스입니다.\n"
    
    has_news = False
    for kw in keywords:
        news_content = get_google_news_yesterday(kw)
        if news_content:
            final_message += news_content
            has_news = True
            
    if has_news:
        send_telegram_message(final_message)
        print("전송 완료")
    else:
        # 어제 뉴스가 하나도 없으면 메시지를 보낼지 말지 결정 (여기선 보냄)
        send_telegram_message(f"😴 '{', '.join(keywords)}' 관련 어제 자 뉴스는 없습니다.")
        print("뉴스 없음")
