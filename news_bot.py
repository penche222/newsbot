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
    # UTC + 9시간 = 한국 시간
    now_kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    yesterday = now_kst - datetime.timedelta(days=1)
    return yesterday.date()

# ==========================================
# 3. 텔레그램 전송 함수 (긴 메시지 자동 분할)
# ==========================================
def send_telegram_message(text):
    """메시지가 4096자를 넘으면 나눠서 보냅니다."""
    if not text.strip(): return # 빈 메시지면 전송 안함

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # 4000자 단위로 자르기 (여유분 두기)
    max_len = 4000
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
            time.sleep(0.5) # 전송 순서 꼬임 방지
        except Exception as e:
            print(f"전송 실패: {e}")

def get_settings_from_pin():
    """고정 메시지 읽기"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat?chat_id={CHAT_ID}"
    stocks = ["삼성전자"]
    filter_keywords = []
    
    try:
        res = requests.get(url).json()
        if "result" in res and "pinned_message" in res["result"]:
            text = res["result"]["pinned_message"]["text"]
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith("종목:") or line.startswith("종목 :"):
                    clean_line = line.replace("종목", "").replace(":", "").strip()
                    stocks = [s.strip() for s in clean_line.split(",") if s.strip()]
                if line.startswith("키워드:") or line.startswith("키워드 :"):
                    clean_line = line.replace("키워드", "").replace(":", "").strip()
                    filter_keywords = [k.strip() for k in clean_line.split(",") if k.strip()]
            return stocks, filter_keywords
    except:
        pass
    return stocks, filter_keywords

# ==========================================
# 4. 뉴스 수집 및 분류 함수
# ==========================================
def fetch_and_classify_news(stocks, filter_keywords):
    """모든 종목의 뉴스를 긁어서 [키워드 뉴스]와 [일반 뉴스]로 나눕니다."""
    
    # 결과 저장소
    all_keyword_news = [] # [{"stock": "삼성", "title": "...", "link": "..."}, ...]
    all_normal_news = {}  # {"삼성": ["뉴스1", "뉴스2"], "SK": ...}
    
    target_date = get_yesterday_range()

    for stock in stocks:
        encoded_keyword = urllib.parse.quote(stock)
        url = f"https://news.google.com/rss/search?q={encoded_keyword}+when:2d&hl=ko&gl=KR&ceid=KR:ko"
        
        try:
            res = requests.get(url)
            root = ET.fromstring(res.content)
            items = root.findall(".//item")
            
            stock_normal_items = [] # 이 종목의 일반 뉴스 임시 저장

            for item in items:
                # 1. 날짜 필터링
                try:
                    from email.utils import parsedate_to_datetime
                    pub_date_str = item.find("pubDate").text
                    article_dt_kst = parsedate_to_datetime(pub_date_str) + datetime.timedelta(hours=9)
                    if article_dt_kst.date() != target_date:
                        continue # 어제 뉴스가 아니면 패스
                except:
                    continue

                # 2. 내용 추출
                title = item.find("title").text
                link = item.find("link").text
                
                # 3. 키워드 매칭 여부 확인
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
                    # 키워드 뉴스에 추가 (종목명, 키워드, 링크 포함)
                    all_keyword_news.append({
                        "stock": stock,
                        "key": matched_key,
                        "content": formatted_link
                    })
                else:
                    # 일반 뉴스에 추가
                    stock_normal_items.append(formatted_link)
            
            # 일반 뉴스는 종목별로 최대 5개만 저장 (너무 많음 방지)
            if stock_normal_items:
                all_normal_news[stock] = stock_normal_items[:5]
                
        except Exception as e:
            print(f"[{stock}] 크롤링 에러: {e}")
            
    return all_keyword_news, all_normal_news

# ==========================================
# 5. 메인 실행
# ==========================================
if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not CHAT_ID:
        exit(1)

    # 1. 설정 가져오기
    stocks, filters = get_settings_from_pin()
    yesterday_str = get_yesterday_range().strftime("%Y-%m-%d")

    # 2. 뉴스 긁어오기 (시간 좀 걸림)
    keyword_news, normal_news = fetch_and_classify_news(stocks, filters)
    
    # -----------------------------------------------------
    # [Part 1] 핵심 키워드 뉴스 리포트 생성
    # -----------------------------------------------------
    report_msg = f"🔥 <b>[핵심 요약] 키워드 뉴스 ({yesterday_str})</b>\n"
    report_msg += f"설정 키워드: {', '.join(filters)}\n\n"
    
    if keyword_news:
        # 종목별로 모으는 게 아니라, 발견된 순서대로(또는 종목별 그룹핑) 보여줌
        # 여기서는 가독성을 위해 '종목명'을 앞에 달아줌
        for item in keyword_news:
            report_msg += f"✅ <b>[{item['stock']}]</b> ({item['key']})\n"
            report_msg += f"└ {item['content']}\n\n"
    else:
        report_msg += "이런... 설정한 키워드에 걸린 뉴스가 하나도 없습니다. 😴\n"
        
    send_telegram_message(report_msg)
    
    # -----------------------------------------------------
    # [Part 2] 일반 뉴스 리포트 생성 (종목별 분류)
    # -----------------------------------------------------
    if normal_news:
        normal_msg = f"📰 <b>[일반 뉴스] 종목별 브리핑</b>\n\n"
        
        for stock, news_list in normal_news.items():
            normal_msg += f"🔹 <b>{stock}</b>\n"
            for news_link in news_list:
                normal_msg += f"- {news_link}\n"
            normal_msg += "\n"
            
        send_telegram_message(normal_msg)
    else:
        send_telegram_message("일반 뉴스도 없습니다.")

    print("전송 완료")
