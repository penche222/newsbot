import requests
import datetime
import os
import urllib.parse
import xml.etree.ElementTree as ET
import time
from email.utils import parsedate_to_datetime # 날짜 파싱용

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
# 3. 텔레그램 전송 (단순 전송 담당)
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
        time.sleep(0.5) # 도배 방지
    except Exception as e:
        print(f"❌ 연결 에러: {e}")

# ==========================================
# 4. 설정 읽기 (유연한 파싱)
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
            
            # 검색 시작 알림 (어제 날짜 표시)
            yst_str = get_yesterday_range().strftime("%Y-%m-%d")
            info_msg = f"🔍 <b>검색 시작 ({yst_str})</b>\n- 종목: {len(stocks)}개\n- 키워드: {', '.join(filter_keywords)}"
            send_telegram_message(info_msg)
            
            return stocks, filter_keywords

    except Exception as e:
        send_telegram_message(f"⚠️ 설정 읽기 실패: {e}")
        
    return stocks, filter_keywords

# ==========================================
# 5. 뉴스 수집 및 분류 (날짜 필터 적용됨)
# ==========================================
def fetch_and_classify_news(stocks, filter_keywords):
    all_keyword_news = [] 
    all_normal_news = {} 
    
    # 어제 날짜 기준
    target_date = get_yesterday_range()

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
                # [수정됨] 날짜 필터링 복구 (어제 뉴스만 통과)
                try:
                    pub_date_str = item.find("pubDate").text
                    article_dt_utc = parsedate_to_datetime(pub_date_str)
                    article_dt_kst = article_dt_utc + datetime.timedelta(hours=9)
                    
                    if article_dt_kst.date() != target_date:
                        continue # 날짜 다르면 건너뜀
                except:
                    continue # 날짜 파싱 실패하면 안전하게 건너뜀

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
# 6. 스마트 버퍼 전송 (군더더기 제거)
# ==========================================
def smart_send(header, news_list, is_keyword_section=True):
    if not news_list: return

    MAX_LENGTH = 3000
    current_buffer = header + "\n\n"
    
    for item in news_list:
        if is_keyword_section:
            line = f"✅ <b>[{item['stock']}]</b> ({item['key']})\n└ {item['content']}\n\n"
        else:
            line = item + "\n"

        if len(current_buffer) + len(line) > MAX_LENGTH:
            send_telegram_message(current_buffer)
            # [수정됨] '(이어서...)' 문구 삭제하고 빈 상태로 시작
            current_buffer = "" 
        
        current_buffer += line
    
    if current_buffer:
        send_telegram_message(current_buffer)

# ==========================================
# 7. 메인 실행
# ==========================================
if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID:
        exit(1)

    stocks, filters = get_settings_from_pin()
    keyword_news, normal_news = fetch_and_classify_news(stocks, filters)
    
    yesterday_str = get_yesterday_range().strftime("%Y-%m-%d")
    
    # [1] 핵심 리포트 전송
    if keyword_news:
        header = f"🔥 <b>핵심 요약 리포트 ({yesterday_str})</b>"
        smart_send(header, keyword_news, is_keyword_section=True)
    else:
        # 키워드 뉴스가 없어도 어제 날짜 확인용으로 메시지는 보냄
        send_telegram_message(f"🔥 핵심 요약: 설정된 키워드 뉴스가 없습니다. ({yesterday_str})")
    
    # [2] 일반 뉴스 전송
    if normal_news:
        flat_normal_list = []
        for stock, items in normal_news.items():
            flat_normal_list.append(f"🔹 <b>{stock}</b>")
            for link in items:
                flat_normal_list.append(f"- {link}")
            flat_normal_list.append("") 
            
        header = f"📰 <b>종목별 일반 뉴스</b>"
        smart_send(header, flat_normal_list, is_keyword_section=False)
    else:
        send_telegram_message(f"📰 일반 뉴스: 검색된 어제 자 기사가 없습니다.")
