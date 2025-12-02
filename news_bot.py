import requests
import datetime
import os
import urllib.parse
import xml.etree.ElementTree as ET

# ==========================================
# 1. 설정
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ==========================================
# 2. 기능 함수들
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
    """고정 메시지 읽기 (진단 기능 강화)"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat?chat_id={CHAT_ID}"
    default_keyword = ["삼성전자"]
    
    print("--- 📡 텔레그램 연결 시도 ---")
    
    try:
        res = requests.get(url).json()
        
        # 1. 채팅방 정보 가져오기 성공 여부
        if "result" not in res:
            print(f"❌ 채팅방 정보 읽기 실패: {res}")
            return default_keyword, False
            
        chat_info = res["result"]
        
        # 2. 고정 메시지가 있는지 확인
        if "pinned_message" not in chat_info:
            print("⚠️ 발견된 고정 메시지가 없습니다.")
            print("👉 팁: 메시지를 보내고, 꾹 눌러서 'Pin(고정)'을 했는지 확인하세요.")
            return default_keyword, False
            
        # 3. 고정 메시지 내용 확인
        raw_text = chat_info["pinned_message"]["text"]
        print(f"📌 봇이 읽은 고정 메시지 내용: '{raw_text}'")
        
        # 4. '설정' 키워드 파싱 (띄어쓰기 무시하도록 개선)
        # "설정: 종목" 또는 "설정 : 종목" 모두 가능하게 처리
        if "설정" in raw_text:
            # 콜론(:)을 기준으로 나눕니다
            if ":" in raw_text:
                targets = raw_text.split(":", 1)[1] # 콜론 뒷부분만 가져옴
            else:
                # 콜론을 안 썼을 경우 ("설정 삼성전자" 처럼)
                targets = raw_text.replace("설정", "")

            # 쉼표로 나누고 공백 제거
            keywords = [k.strip() for k in targets.split(",") if k.strip()]
            
            if keywords:
                print(f"✅ 적용된 검색어: {keywords}")
                return keywords, True
            else:
                print("⚠️ '설정:' 뒤에 종목명이 비어있습니다.")
        else:
            print("⚠️ 고정 메시지에 '설정'이라는 단어가 포함되지 않았습니다.")
            
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        
    print("👉 기본값(삼성전자)으로 진행합니다.")
    return default_keyword, False

def get_google_news(keyword):
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        res = requests.get(url)
        root = ET.fromstring(res.content)
        items = root.findall(".//item")
        
        if not items: return None

        result_text = f"\n🔍 <b>[{keyword}]</b>\n"
        for i, item in enumerate(items):
            if i >= 3: break
            title = item.find("title").text
            link = item.find("link").text
            result_text += f"- <a href='{link}'>{title}</a>\n"
        return result_text

    except Exception as e:
        print(f"크롤링 에러 ({keyword}): {e}")
        return None

# ==========================================
# 3. 메인 실행
# ==========================================
if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Secrets 설정 오류")
        exit(1)

    keywords, is_custom = get_keywords()
    
    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    final_message = f"📰 <b>뉴스 브리핑 ({today})</b>\n"
    
    if not is_custom:
         final_message += "(⚠️ 설정 오류: 봇이 고정 메시지를 못 읽어서 기본값으로 검색했습니다. GitHub 로그를 확인하세요)\n"

    has_news = False
    for kw in keywords:
        news_content = get_google_news(kw)
        if news_content:
            final_message += news_content
            has_news = True
            
    if has_news:
        send_telegram_message(final_message)
    else:
        send_telegram_message(f"오늘은 '{', '.join(keywords)}' 관련 뉴스가 없습니다.")
