import requests
import datetime
import os
import urllib.parse
import xml.etree.ElementTree as ET
import time

# ==========================================
# 1. 설정
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ==========================================
# 2. 텔레그램 전송 (단순 전송만 담당)
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
        res = requests.post(url, json=payload)
        # 만약 전송 실패하면 로그 출력
        if res.status_code != 200:
            print(f"❌ 전송 실패 (코드 {res.status_code}): {res.text}")
        time.sleep(0.5) # 도배 방지
    except Exception as e:
        print(f"❌ 연결 에러: {e}")

# ==========================================
# 3. 설정 읽기 (유연한 파싱)
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
            
            # 검색 시작 알림
            info_msg = f"🔍 <b>검색 시작</b>\n- 종목: {len(stocks)}개\n- 키워드: {', '.join(filter_keywords)}"
            send_telegram_message(info_msg)
            
            return stocks, filter_keywords

    except Exception as e:
        send_telegram_message(f"⚠️ 설정 읽기 실패: {e}")
        
    return stocks, filter_keywords

# ==========================================
# 4. 뉴스 수집 및 분류
# ==========================================
def fetch_and_classify_news(stocks, filter_keywords):
    all_keyword_news = [] 
    all_normal_news = {} 

    for i, stock in enumerate(stocks):
        if i > 0: time.sleep(1.5) # 구글 차단 방지
        
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

            for item in items:
                title = item.find("title").text
                link = item.find("link").text
                
                is_matched = False
                matched_key = ""
                if filter_keywords:
                    for key in filter_keywords:
                        if key in title:
                            is_matched = True
                            matched_key = key
                            break
                
                # HTML 링크 미리 생성
                formatted_link = f"<a href='{link}'>{title}</a>"

                if is_matched:
                    all_keyword_news.append({
                        "stock": stock,
                        "key": matched_key,
                        "content": formatted_link
                    })
                else:
                    stock_normal_items.append(formatted_link)
            
            if stock_normal_items:
                all_normal_news[stock] = stock_normal_items[:5]
                
        except Exception as e:
            print(f"[{stock}] 에러: {e}")
            continue
            
    return all_keyword_news, all_normal_news

# ==========================================
# 5. 스마트 버퍼 전송 (★핵심 기능)
# ==========================================
def smart_send(header, news_list, is_keyword_section=True):
    """
    메시지를 벽돌 쌓듯이 하나씩 더하다가,
    꽉 차면(3000자) 보내고 새 종이를 꺼내는 함수
    """
    if not news_list: return

    # 안전하게 3000자로 제한 (텔레그램 최대는 4096)
    MAX_LENGTH = 3000
    
    current_buffer = header + "\n\n"
    
    for item in news_list:
        # 한 줄 만들기
        if is_keyword_section:
            # 키워드 뉴스 포맷
            line = f"✅ <b>[{item['stock']}]</b> ({item['key']})\n└ {item['content']}\n\n"
        else:
            # 일반 뉴스 포맷 (item 자체가 문자열)
            line = item + "\n"

        # ★ 만약 이번 줄을 더했을 때 3000자가 넘으면? -> 전송하고 비움
        if len(current_buffer) + len(line) > MAX_LENGTH:
            send_telegram_message(current_buffer)
            current_buffer = "🚀 <b>(이어서...)</b>\n\n" # 다음 페이지 제목
        
        # 버퍼에 추가
        current_buffer += line
    
    # 남은 내용 전송
    if current_buffer:
        send_telegram_message(current_buffer)

# ==========================================
# 6. 메인 실행
# ==========================================
if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID:
        exit(1)

    stocks, filters = get_settings_from_pin()
    keyword_news, normal_news = fetch_and_classify_news(stocks, filters)
    
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # [1] 핵심 리포트 전송 (스마트 버퍼 사용)
    if keyword_news:
        header = f"🔥 <b>핵심 요약 리포트 ({today_str})</b>"
        smart_send(header, keyword_news, is_keyword_section=True)
    else:
        send_telegram_message(f"🔥 핵심 요약: 설정된 키워드 뉴스가 없습니다.")
    
    # [2] 일반 뉴스 전송 (스마트 버퍼 사용)
    # 일반 뉴스는 종목별로 묶어서 리스트를 평탄화(Flatten)해야 함
    if normal_news:
        flat_normal_list = []
        for stock, items in normal_news.items():
            flat_normal_list.append(f"🔹 <b>{stock}</b>")
            for link in items:
                flat_normal_list.append(f"- {link}")
            flat_normal_list.append("") # 공백 줄
            
        header = f"📰 <b>종목별 일반 뉴스</b>"
        smart_send(header, flat_normal_list, is_keyword_section=False)
    else:
        send_telegram_message("📰 일반 뉴스: 검색된 기사가 없습니다.")
