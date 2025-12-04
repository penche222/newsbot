import requests
import datetime
import os
import urllib.parse
import xml.etree.ElementTree as ET
import time
import re
import difflib
from email.utils import parsedate_to_datetime

# ==========================================
# 1. 설정
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ==========================================
# 2. 날짜 계산 (어제 00:00 ~ 23:59)
# ==========================================
def get_yesterday_range():
    now_kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    yesterday = now_kst - datetime.timedelta(days=1)
    return yesterday.date()

# ==========================================
# 3. 텔레그램 전송
# ==========================================
def send_telegram_message(text):
    if not text.strip(): return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload)
        time.sleep(0.5)
    except Exception as e:
        print(f"❌ 연결 에러: {e}")

# ==========================================
# 4. 설정 읽기 (알림 메시지 삭제됨)
# ==========================================
def get_settings_from_pin():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat?chat_id={CHAT_ID}"
    stocks = ["삼성전자"]
    filter_keywords = []
    
    try:
        res = requests.get(url).json()
        if "result" in res and "pinned_message" in res["result"]:
            raw_text = res["result"]["pinned_message"]["text"]
            lines = raw_text.split('\n')
            
            temp_stocks = []
            temp_keywords = []
            current_mode = None

            for line in lines:
                line = line.strip()
                if not line: continue 
                
                if "종목" in line and ":" in line:
                    current_mode = "stock"
                    content = line.split(":", 1)[1]
                    temp_stocks.extend(content.split(","))
                    continue
                elif "키워드" in line and ":" in line:
                    current_mode = "keyword"
                    content = line.split(":", 1)[1]
                    temp_keywords.extend(content.split(","))
                    continue
                
                if current_mode == "stock": temp_stocks.extend(line.split(","))
                elif current_mode == "keyword": temp_keywords.extend(line.split(","))

            stocks = [s.strip() for s in temp_stocks if s.strip()]
            filter_keywords = [k.strip() for k in temp_keywords if k.strip()]
            
            # [삭제됨] "검색 시작" 알림 메시지 부분 제거
            # 조용히 설정값만 반환합니다.
            return stocks, filter_keywords

    except Exception as e:
        # 에러 날 때만 알려줌
        send_telegram_message(f"⚠️ 설정 읽기 실패: {e}")
        
    return stocks, filter_keywords

# ==========================================
# 5. 유사도 검사 및 필터링
# ==========================================
def clean_title_for_compare(title):
    title = re.sub(r'\[.*?\]', '', title) 
    title = re.sub(r'\(.*?\)', '', title)
    title = re.sub(r'[^\w\s]', '', title)
    return title.strip().replace(" ", "")

def is_similar_news(new_title, existing_titles):
    target = clean_title_for_compare(new_title)
    for exist in existing_titles:
        compared = clean_title_for_compare(exist)
        similarity = difflib.SequenceMatcher(None, target, compared).ratio()
        if similarity > 0.6: return True
    return False

# ==========================================
# 6. 뉴스 수집 및 분류 (페스티벌 차단 추가)
# ==========================================
def fetch_and_classify_news(stocks, filter_keywords):
    all_keyword_news = {} 
    all_normal_news = {} 
    
    target_date = get_yesterday_range()
    
    # ★ 노이즈 필터 리스트
    NOISE_WORDS = [
        # 1. 쓸모없는 카테고리
        "포토", "화보", "사진", "스포츠", "연예", "부고", "인사", "동영상", "오늘의", "미리보는",
        # 2. 스포츠 관련
        "야구", "축구", "농구", "배구", "골프", "올림픽", "월드컵", "선수", "경기", "리그", "우승", "감독", "시구", 
        "연승", "연패",
        # 3. 사회활동/CSR/수상/축제 관련
        "사회공헌", "봉사", "나눔", "기부", "성금", "캠페인", "후원", "장학", "지원사업", "CSR", "플로깅", "연탄",
        "수상", "대상", "표창", "선정", "페스티벌", "박람회", "전시회", # [NEW] 페스티벌, 박람회 추가됨
        # 4. 마케팅/이벤트/혜택/론칭 관련
        "이벤트", "프로모션", "혜택", "할인", "적립", "경품", "사은품", "특가", "기획전", "쿠폰", "체험단", "오픈런", "페이백", "출시기념",
        "론칭", "런칭", "오픈", "개장", "입점"
    ]

    for i, stock in enumerate(stocks):
        if i > 0: time.sleep(1.5)
        
        encoded_keyword = urllib.parse.quote(stock)
        url = f"https://news.google.com/rss/search?q={encoded_keyword}+when:2d&hl=ko&gl=KR&ceid=KR:ko"
        
        try:
            res = requests.get(url, timeout=10)
            if res.status_code != 200: continue
            
            try:
                root = ET.fromstring(res.content)
            except: continue

            items = root.findall(".//item")
            stock_normal_items = []
            stock_keyword_items = []
            seen_titles = []

            for item in items:
                try:
                    pub_date_str = item.find("pubDate").text
                    article_dt_utc = parsedate_to_datetime(pub_date_str)
                    article_dt_kst = article_dt_utc + datetime.timedelta(hours=9)
                    if article_dt_kst.date() != target_date: continue 
                except: continue

                title = item.find("title").text.strip()
                link = item.find("link").text
                
                # --- [강력한 필터링] ---
                if any(noise in title for noise in NOISE_WORDS): continue
                if stock not in title: continue
                if is_similar_news(title, seen_titles): continue
                
                seen_titles.append(title)

                # --- [분류] ---
                is_matched = False
                matched_key = ""
                if filter_keywords:
                    for key in filter_keywords:
                        if key in title:
                            is_matched = True
                            matched_key = key
                            break
                
                formatted_link = f"<a href='{link}'>{title}</a>"

                if is_matched:
                    stock_keyword_items.append(f"({matched_key}) {formatted_link}")
                else:
                    stock_normal_items.append(formatted_link)
            
            if stock_keyword_items:
                all_keyword_news[stock] = stock_keyword_items
                
            if stock_normal_items:
                all_normal_news[stock] = stock_normal_items[:3]
                
        except Exception as e:
            print(f"[{stock}] 에러: {e}")
            continue
            
    return all_keyword_news, all_normal_news

# ==========================================
# 7. 스마트 버퍼 전송
# ==========================================
def smart_send(header, lines):
    if not lines: return
    MAX_LENGTH = 3000
    current_buffer = header + "\n\n"
    
    for line in lines:
        if len(current_buffer) + len(line) > MAX_LENGTH:
            send_telegram_message(current_buffer)
            current_buffer = "" 
        current_buffer += line + "\n"
    
    if current_buffer.strip():
        send_telegram_message(current_buffer)

# ==========================================
# 8. 메인 실행
# ==========================================
if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID: exit(1)

    stocks, filters = get_settings_from_pin()
    keyword_news, normal_news = fetch_and_classify_news(stocks, filters)
    yesterday_str = get_yesterday_range().strftime("%Y-%m-%d")
    
    # [1] 핵심 리포트
    if keyword_news:
        header = f"🔥 <b>핵심 요약 리포트 ({yesterday_str})</b>"
        flat_keyword_list = []
        for stock, items in keyword_news.items():
            flat_keyword_list.append(f"✅ <b>[{stock}]</b>")
            for item in items: flat_keyword_list.append(f"└ {item}")
            flat_keyword_list.append("")
        smart_send(header, flat_keyword_list)
    else:
        # 뉴스 없으면 조용히 종료 (아무 메시지도 안 보냄)
        pass
    
    # [2] 일반 뉴스
    if normal_news:
        header = f"📰 <b>일반 뉴스 (Top 3)</b>"
        flat_normal_list = []
        for stock, items in normal_news.items():
            flat_normal_list.append(f"🔹 <b>{stock}</b>")
            for item in items: flat_normal_list.append(f"- {item}")
            flat_normal_list.append("")
        smart_send(header, flat_normal_list)
    else:
        # 뉴스 없으면 조용히 종료
        pass
