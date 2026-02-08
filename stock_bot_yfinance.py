import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime

# ========== 설정 (환경 변수 권장) ==========
# Render 설정에서 아래 이름으로 변수를 등록하세요.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 관심 종목 설정
INTEREST_STOCKS_KR = {"005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "035420.KS": "NAVER"}
INTEREST_STOCKS_US = {"AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "TSLA": "테슬라"}
INTEREST_STOCKS_HK = {"9988.HK": "알리바바", "0700.HK": "텐센트", "1810.HK": "샤오미"}

def send_telegram_message(message):
    """텔레그램으로 메시지 전송"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ 토큰이나 채팅 ID가 설정되지 않았습니다.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print(f"✅ 전송 성공: {datetime.now()}")
        else:
            print(f"❌ 전송 실패: {response.text}")
    except Exception as e:
        print(f"❌ 오류: {e}")

def get_exchange_rates():
    """환율 조회 (USD, JPY, HKD)"""
    try:
        url = "https://open.er-api.com/v6/latest/USD" # 좀 더 안정적인 API로 변경
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()['rates']
            usd_krw = data.get('KRW', 0)
            jpy_rate = data.get('JPY', 0)
            hkd_rate = data.get('HKD', 0)
            return {
                'usd_krw': round(usd_krw, 2),
                'jpy_krw': round((usd_krw / jpy_rate) * 100, 2),
                'hkd_krw': round(usd_krw / hkd_rate, 2)
            }
    except Exception as e:
        print(f"❌ 환율 오류: {e}")
    return None

def get_stock_info_with_returns(symbol, name, market="US"):
    """주식 정보 및 다각도 수익률 계산"""
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="1y")
        if hist.empty: return None

        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        
        # 수익률 계산 함수
        def calc_ret(past_price):
            return ((current_price - past_price) / past_price * 100) if past_price else 0

        ytd_price = hist[hist.index.year == datetime.now().year]['Close'].iloc[0]
        
        # 시장별 포맷 설정
        fmt = "{:,.0f}" if market == "KR" else "{:.2f}"
        unit = "원" if market == "KR" else ("HKD" if market == "HK" else "USD")

        return {
            'name': name,
            'price': fmt.format(current_price),
            'rate': f"{calc_ret(prev_close):+.2f}",
            'week': f"{calc_ret(hist['Close'].iloc[-5] if len(hist)>5 else hist['Close'].iloc[0]):+.2f}",
            'month': f"{calc_ret(hist['Close'].iloc[-21] if len(hist)>21 else hist['Close'].iloc[0]):+.2f}",
            'ytd': f"{calc_ret(ytd_price):+.2f}",
            'unit': unit
        }
    except: return None

def create_daily_report():
    """종합 리포트 생성"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"🌍 <b>글로벌 주식 리포트 ({now})</b>\n" + "="*25 + "\n"
    
    # 환율 정보 추가
    ex = get_exchange_rates()
    if ex:
        msg += f"💱 USD: {ex['usd_krw']} | JPY: {ex['jpy_krw']} | HKD: {ex['hkd_krw']}\n\n"

    # 섹션별 데이터 수집 (한국/미국/홍콩 순회하며 msg에 추가하는 로직 유지)
    # ... (기존 create_daily_report의 루프 구조와 동일하게 작성)
    # 가독성을 위해 생략되었으나, 위 get_stock_info_with_returns 데이터를 활용해 구성하시면 됩니다.
    
    msg += "\n📊 수익률: 일 / 주 / 월 / YTD"
    return msg

def job():
    report = create_daily_report()
    send_telegram_message(report)

if __name__ == "__main__":
    # 스케줄 설정 (기존 코드와 동일)
    schedule.every().day.at("09:00").do(job)
    # 서버 유지를 위한 무한 루프
    while True:
        schedule.run_pending()
        time.sleep(60)
