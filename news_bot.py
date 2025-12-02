import requests
import datetime
import os
import urllib.parse
import xml.etree.ElementTree as ET
import json

# ==========================================
# 1. 설정
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

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
    except:
        return None

# ==========================================
# 메인 실행 (진단 모드)
# ==========================================
if __name__ == "__main__":
    
    # 1. 봇이 보는 채널 정보 가져오기
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat?chat_id={CHAT_ID}"
    res = requests.get(url).json()
    
    debug_msg = "🕵️‍♂️ <b>[봇의 시야 확인]</b>\n"
    
    # 2. 분석 결과 보고
    if "result" in res:
        chat_info = res["result"]
        chat_type = chat_info.get("type", "알수없음")
        debug_msg += f"- 방 타입: {chat_type}\n"
        
        # 고정 메시지가 있는지 확인
        if "pinned_message" in chat_info:
            pinned_text = chat_info["pinned_message"]["text"]
            debug_msg += f"- 고정 메시지 발견됨: O\n"
            debug_msg += f"- 내용: <b>'{pinned_text}'</b>\n"
            
            # 키워드 추출 시도
            if "설정" in pinned_text:
                targets = pinned_text.split("설정")[1].replace(":", "").strip()
                keywords = [k.strip() for k in targets.split(",") if k.strip()]
                debug_msg += f"- 추출된 키워드: {keywords}\n"
                final_keywords = keywords
            else:
                debug_msg += "- ⚠️ 내용에 '설정'이라는 글자가 없음\n"
                final_keywords = ["삼성전자"]
        else:
            debug_msg += "- ❌ 고정 메시지가 안 보임 (권한 문제 or 핀 안함)\n"
            final_keywords = ["삼성전자"]
    else:
        debug_msg += f"- ❌ 정보 조회 실패: {res}\n"
        final_keywords = ["삼성전자"]

    # 3. 진단 결과 전송 (텔레그램으로 범인을 알려줌)
    send_telegram_message(debug_msg)

    # 4. 뉴스 전송 (추출된 키워드 or 기본값)
    full_news = ""
    for kw in final_keywords:
        news = get_google_news(kw)
        if news: full_news += news
        
    if full_news:
        send_telegram_message(full_news)
