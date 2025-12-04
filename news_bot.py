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
# 2. 날짜 계산 (어제 날짜)
# ==========================================
def get_yesterday_range():
    now_kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    yesterday = now_kst - datetime.timedelta(days=1)
    return yesterday.date()

# ==========================================
# 3. 텔레그램 전송 함수 (4096자 제한 대응)
# ==========================================
def send_telegram_message(text):
    if not text.strip(): return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # 3500자 단위로 안전하게 자름
    max_len = 3500
    for i in range(0, len(text), max_len):
        chunk = text[i:i+max_len]
        payload = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            requests.post(url, json=payload)
            time.sleep(1) # 메시지 전송 사이에도 쉼
        except Exception as e:
            print(f"전송 실패: {e}")

def get_settings_from_pin():
    """줄바꿈, 콤마, 들여쓰기 등 개떡같이 써도 찰떡같이 알아듣는 파서"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat?chat_id={CHAT_ID}"
    
    stocks = ["삼성전자"]
    filter_keywords = []
    
    try:
        res = requests.get(url).json()
        if "result" in res and "pinned_message" in res["result"]:
            raw_text = res["result"]["pinned_message"]["text"]
            
            # --- 파싱 로직 시작 ---
            lines = raw_text.split('\n')
            current_mode = None # 지금 읽는 줄이 종목인지 키워드인지 기억
            
            temp_stocks = []
            temp_keywords = []

            for line in lines:
                line = line.strip()
                if not line: continue # 빈 줄 무시

                # '종목' 이라는 단어가 포함된 줄을 만나면 모드 변경
                if "종목" in line and ":" in line:
                    current_mode = "stock"
                    # "종목 : 삼성전자" -> "삼성전자" 추출
                    content = line.split(":", 1)[1]
                    temp_stocks.extend(content.split(","))
                    continue
                
                # '키워드' 라는 단어가 포함된 줄을 만나면 모드 변경
                elif "키워드" in line and ":" in line:
                    current_mode = "keyword"
                    content = line.split(":", 1)[1]
                    temp_keywords.extend(content.split(","))
                    continue
                
                # 헤더가 없는 줄은 현재 모드에 따라 추가 (줄바꿈 지원)
                if current_mode == "stock":
                    temp_stocks.extend(line.split(","))
                elif current_mode == "keyword":
                    temp_keywords.extend(line.split(","))

            # 공백 제거 및 빈 값 제거
            stocks = [s.strip() for s in temp_stocks if s.strip()]
            filter_keywords = [k.strip() for k in temp_keywords if k.strip()]
            
            # (디버깅용) 텔레그램으로 인식 결과 알려줌
            return stocks, filter_keywords, True

    except Exception as e:
        print(f"설정 파싱 에러: {e}")
        pass
        
    return stocks, filter_keywords, False

# ==========================================
# 4. 뉴스 수집 및 분류
# ==========================================
def fetch_and_classify_news(stocks, filter_keywords):
    all_keyword_news = [] 
    all_normal_news = {} 
    
    target_date = get_yesterday_range()

    # ★ 봇이 인식한 종목 리스트를 먼저 보여줌 (확인용)
    intro = f"🔍 <b>검색 시작</b>\n대상 종목({len(stocks)}개): {', '.join(stocks)}\n"
    if filter_keywords:
        intro += f"필터 키워드: {', '.join(filter_keywords)}"
    send_telegram_message(intro)

    for i, stock in enumerate(stocks):
        # ★ 핵심: 구글 차단 방지를 위해 종목마다 2초씩 쉼
        if i > 0: time.sleep(2)
        
        encoded_keyword = urllib.parse.quote(stock)
        url = f"https://news.google.com/rss/search?q={encoded_keyword}+when:2d&hl=ko&gl=KR&ceid=KR:ko"
        
        try:
            res = requests.get(url, timeout=10) # 타임아웃 설정
            root = ET.fromstring(res.content)
            items = root.findall(".//item")
            
            stock_normal_items = []

            for item in items:
                # 날짜 필터링
                try:
                    from email.utils import parsedate_to_datetime
                    pub_date_str = item.find("pubDate").text
                    article_dt_kst = parsedate_to_datetime(pub_date_str) + datetime.timedelta(hours=9)
                    if article_dt_kst.date() != target_date:
                        continue 
                except:
                    continue

                title = item.find("title").text
                link = item.find("link").text
                
                # 키워드 매칭
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
            
            # 일반 뉴스는 5개까지만
            if stock_normal_items:
                all_normal_news[stock] = stock_normal_items[:5]
                
        except Exception as e:
            print(f"[{stock}] 실패: {e}")
            # 실패해도 다음 종목으로 넘어감
            continue
            
    return all_keyword_news, all_normal_news

# ==========================================
# 5. 메인 실행
# ==========================================
if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID:
        exit(1)

    stocks, filters, is_valid = get_settings_from_pin()
    
    if not is_valid:
        # 고정 메시지를 못 읽었을 때 경고
        send_telegram_message("⚠️ 설정을 읽지 못해 기본값(삼성전자)으로 검색합니다.\n고정 메시지 형식을 확인하세요.")

    keyword_news, normal_news = fetch_and_classify_news(stocks, filters)
    yesterday_str = get_yesterday_range().strftime("%Y-%m-%d")
    
    # [1] 핵심 리포트
    report_msg = f"🔥 <b>핵심 요약 리포트 ({yesterday_str})</b>\n\n"
    
    if keyword_news:
        for item in keyword_news:
            report_msg += f"✅ <b>[{item['stock']}]</b> ({item['key']})\n"
            report_msg += f"└ {item['content']}\n\n"
        send_telegram_message(report_msg)
    else:
        send_telegram_message(f"🔥 핵심 요약: 설정된 키워드({', '.join(filters)}) 뉴스가 없습니다.")
    
    # [2] 일반 뉴스
    if normal_news:
        normal_msg = f"📰 <b>종목별 일반 뉴스</b>\n\n"
        for stock, news_list in normal_news.items():
            normal_msg += f"🔹 <b>{stock}</b>\n"
            for news_link in news_list:
                normal_msg += f"- {news_link}\n"
            normal_msg += "\n"
        send_telegram_message(normal_msg)
    else:
        send_telegram_message("📰 일반 뉴스: 검색된 기사가 없습니다.")
