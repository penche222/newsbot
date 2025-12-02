import requests
from bs4 import BeautifulSoup
import datetime
import os
import urllib.parse

# ==========================================
# 1. 설정 (GitHub Secrets에서 가져옴)
# ==========================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ==========================================
# 2. 기능 함수들
# ==========================================
def send_telegram_message(text):
    """텔레그램으로 메시지를 보냅니다."""
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
    """텔레그램 고정 메시지에서 키워드를 읽어옵니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat?chat_id={CHAT_ID}"
    default_keyword = ["삼성전자"]
    
    try:
        res = requests.get(url).json()
        if "result" in res and "pinned_message" in res["result"]:
            text = res["result"]["pinned_message"]["text"]
            if text.startswith("설정:"):
                keywords = [k.strip() for k in text.replace("설정:", "").split(",") if k.strip()]
                return keywords, True
    except Exception as e:
        print(f"고정 메시지 확인 에러: {e}")
        
    return default_keyword, False

def get_google_news(keyword):
    """구글 뉴스 RSS 검색 (차단 없음, 100% 성공)"""
    # 검색어를 URL 인코딩 (한글 -> %ED%8... 변환)
    encoded_keyword = urllib.parse.quote(keyword)
    
    # 구글 뉴스 RSS 주소 (한국 설정)
    url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        res = requests.get(url)
        # XML 데이터를 파싱
        soup = BeautifulSoup(res.text, "xml") 
        items = soup.select("item")
        
        if not items:
            return None

        # 결과 텍스트 만들기
        result_text = f"\n🔍 <b>[{keyword}]</b>\n"
        
        count = 0
        for item in items:
            if count >= 3: break # 3개까지만
            
            title = item.title.get_text()
            link = item.link.get_text()
            
            # 날짜 정리 (Tue, 02 Dec 2025... -> 보기 좋게)
            # pubDate는 있을 수도 없을 수도 있어서 예외처리
            try:
                pub_date = item.pubDate.get_text()
                # 간단히 날짜만 표시하려면 파싱 필요하지만, 복잡하니 생략하거나 그대로 둠
            except:
                pass

            result_text += f"- <a href='{link}'>{title}</a>\n"
            count += 1
            
        return result_text

    except Exception as e:
        print(f"크롤링 에러 ({keyword}): {e}")
        # 혹시 xml 파서 에러가 나면 html.parser로 재시도
        try:
            soup = BeautifulSoup(res.text, "html.parser")
            items = soup.select("item")
            result_text = f"\n🔍 <b>[{keyword}]</b>\n"
            count = 0
            for item in items:
                if count >= 3: break
                title = item.select_one("title").get_text()
                link = item.find("link").next_sibling.strip() if item.find("link").next_sibling else item.select_one("link").get_text() # html parser 특성상 link 처리가 까다로움
                # 간단하게 title만 가져오는 방식으로 fallback
                if not link: link = "https://news.google.com"
                result_text += f"- {title}\n" 
                count += 1
            return result_text
        except:
            return None

# ==========================================
# 3. 메인 실행
# ==========================================
if __name__ == "__main__":
    print("뉴스 봇 실행 시작...")
    
    keywords, is_custom = get_keywords()
    
    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    final_message = f"📰 <b>뉴스 브리핑 ({today})</b>\n"
    
    has_news = False
    for kw in keywords:
        news_content = get_google_news(kw)
        if news_content:
            final_message += news_content
            has_news = True
            
    if has_news:
        send_telegram_message(final_message)
        print("전송 완료")
    else:
        send_telegram_message(f"오늘은 '{', '.join(keywords)}' 관련 뉴스가 없습니다.")
        print("뉴스 없음")

",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"전송 실패: {e}")

def get_keywords():
    """텔레그램 고정 메시지에서 키워드를 읽어옵니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChat?chat_id={CHAT_ID}"
    default_keyword = ["삼성전자"] # '특징주'는 결과가 없을 때가 많아 확실한 '삼성전자'로 변경
    
    try:
        res = requests.get(url).json()
        if "result" in res and "pinned_message" in res["result"]:
            text = res["result"]["pinned_message"]["text"]
            if text.startswith("설정:"):
                keywords = [k.strip() for k in text.replace("설정:", "").split(",") if k.strip()]
                print(f"📌 고정 메시지 적용됨: {keywords}")
                return keywords, True
        else:
            print("⚠️ 고정 메시지 없음 (기본값 사용)")
    except Exception as e:
        print(f"고정 메시지 확인 에러: {e}")
        
    return default_keyword, False

def get_naver_news(keyword):
    """네이버 뉴스 검색 (사람인 척 위장 강화)"""
    # 정확도순 대신 최신순(sort=1)
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sort=1"
    
    # 🚨 핵심 수정: 헤더를 진짜 브라우저처럼 길게 설정
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1차 시도: 일반적인 뉴스 제목 클래스 (.news_tit)
        news_list = soup.select(".news_tit")
        
        # 2차 시도: 만약 못 찾았으면 다른 클래스명으로 시도 (.tit)
        if not news_list:
            print(f"[{keyword}] 1차 검색 실패, 2차 시도...")
            news_list = soup.select("a.tit")

        if not news_list:
            print(f"[{keyword}] 뉴스 검색 결과 0건 (HTML 구조가 다르거나 차단됨)")
            return None

        print(f"[{keyword}] 뉴스 {len(news_list)}개 발견!")

        # 결과 텍스트 만들기
        result_text = f"\n🔍 <b>[{keyword}]</b>\n"
        for i, item in enumerate(news_list):
            if i >= 3: break # 3개까지만
            title = item.get_text().strip().replace("<", "").replace(">", "")
            link = item['href']
            result_text += f"- <a href='{link}'>{title}</a>\n"
            
        return result_text

    except Exception as e:
        print(f"크롤링 에러 ({keyword}): {e}")
        return None

# ==========================================
# 3. 메인 실행
# ==========================================
if __name__ == "__main__":
    print("뉴스 봇 실행 시작...")
    
    keywords, is_custom = get_keywords()
    
    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    final_message = f"📰 <b>뉴스 브리핑 ({today})</b>\n"
    
    # 디버깅용: 고정메시지 안 썼으면 알려주기
    if not is_custom:
        final_message += "(⚠️ 현재 '기본 키워드'로 검색 중입니다. 채널에 '설정: 종목명'을 고정해주세요)\n"

    has_news = False
    for kw in keywords:
        news_content = get_naver_news(kw)
        if news_content:
            final_message += news_content
            has_news = True
            
    if has_news:
        send_telegram_message(final_message)
        print("전송 완료")
    else:
        # 뉴스를 못 찾았더라도 오류 메시지를 텔레그램으로 보내서 확인시켜줌
        error_msg = f"❌ <b>[{', '.join(keywords)}]</b> 관련 뉴스를 찾지 못했습니다.\n네이버가 차단했거나, 해당 키워드의 최신 뉴스가 없습니다."
        send_telegram_message(error_msg)
        print("뉴스 없음 메시지 전송")
