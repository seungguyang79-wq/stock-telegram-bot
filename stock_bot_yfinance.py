"""
주식 정보 텔레그램 알림 봇 (yfinance 버전)
- yfinance 라이브러리 사용으로 안정성 향상
- API 제한 문제 해결
- 한국, 미국, 홍콩 시장 지수
- 수익률 분석 포함
"""
import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime, timedelta

# ========== 설정 ==========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "417485629")

# 관심 종목 설정 (개수를 줄였습니다)
INTEREST_STOCKS_KR = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "035420.KS": "NAVER"
}

# 미국 주식
INTEREST_STOCKS_US = {
    "AAPL": "애플",
    "MSFT": "마이크로소프트",
    "NVDA": "엔비디아",
    "TSLA": "테슬라"
}

# 홍콩 주식
INTEREST_STOCKS_HK = {
    "9988.HK": "알리바바",
    "0700.HK": "텐센트",
    "1810.HK": "샤오미"
}

# ========== 텔레그램 메시지 전송 함수 ==========
def send_telegram_message(message):
    """텔레그램으로 메시지 전송"""
    url = f"https://api.telegram.org/bot8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s/sendMessage"
    payload = {
        "chat_id": 417485629,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print(f"✅ 메시지 전송 성공: {datetime.now()}")
        else:
            print(f"❌ 메시지 전송 실패: {response.text}")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


# ========== 환율 정보 가져오기 ==========
def get_exchange_rates():
    """달러, 엔화, 홍콩달러 환율 조회"""
    try:
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            usd_to_krw = data['usd'].get('krw', 0)
            jpy_rate = data['usd'].get('jpy', 0)
            hkd_to_krw = data['usd'].get('hkd', 0)
            
            jpy_krw_rate = (usd_to_krw / jpy_rate) * 100 if jpy_rate > 0 else 0
            hkd_krw_rate = (usd_to_krw / hkd_to_krw) if hkd_to_krw > 0 else 0
            
            return {
                'usd_krw': round(usd_to_krw, 2),
                'jpy_krw': round(jpy_krw_rate, 2),
                'hkd_krw': round(hkd_krw_rate, 2)
            }
    except Exception as e:
        print(f"❌ 환율 조회 오류: {e}")
        return None


# ========== yfinance로 주식 정보 및 수익률 조회 ==========
def get_stock_info_with_returns(symbol, name, market="US"):
    """yfinance를 사용한 주식 정보 및 수익률 조회"""
    try:
        print(f"📊 {name} 조회 중...")
        
        # yfinance로 데이터 가져오기
        stock = yf.Ticker(symbol)
        
        # 1년치 일간 데이터
        hist = stock.history(period="1y", interval="1d")
        
        if hist.empty:
            print(f"❌ {name} 데이터 없음")
            return None
        
        # 현재가 (가장 최근 종가)
        current_price = hist['Close'].iloc[-1]
        
        # 전일 종가
        if len(hist) > 1:
            previous_close = hist['Close'].iloc[-2]
        else:
            previous_close = current_price
        
        # 일간 수익률
        daily_change = current_price - previous_close
        daily_return = (daily_change / previous_close * 100) if previous_close else 0
        
        # 주간 수익률 (7일 전)
        if len(hist) >= 7:
            week_price = hist['Close'].iloc[-7]
            week_return = ((current_price - week_price) / week_price * 100)
        else:
            week_return = 0
        
        # 월간 수익률 (30일 전)
        if len(hist) >= 30:
            month_price = hist['Close'].iloc[-30]
            month_return = ((current_price - month_price) / month_price * 100)
        else:
            month_return = 0
        
        # YTD 수익률 (올해 첫 거래일)
        current_year = datetime.now().year
        ytd_data = hist[hist.index.year == current_year]
        if not ytd_data.empty:
            ytd_price = ytd_data['Close'].iloc[0]
            ytd_return = ((current_price - ytd_price) / ytd_price * 100)
        else:
            ytd_return = 0
        
        # 연간 수익률 (1년 전, 또는 가능한 가장 오래된 데이터)
        if len(hist) >= 252:  # 대략 1년치 거래일
            year_price = hist['Close'].iloc[0]
            year_return = ((current_price - year_price) / year_price * 100)
        else:
            year_return = 0
        
        # 통화 단위
        if market == "KR":
            currency = "원"
            price_format = f"{current_price:,.0f}"
        elif market == "HK":
            currency = "HKD"
            price_format = f"{current_price:.2f}"
        else:
            currency = "USD"
            price_format = f"{current_price:.2f}"
        
        print(f"✅ {name} 완료: {price_format} {currency}")
        
        return {
            'name': name,
            'price': price_format,
            'change': f"{daily_change:+.2f}",
            'rate': f"{daily_return:+.2f}",
            'week_return': f"{week_return:+.2f}",
            'month_return': f"{month_return:+.2f}",
            'ytd_return': f"{ytd_return:+.2f}",
            'year_return': f"{year_return:+.2f}",
            'currency': currency
        }
        
    except Exception as e:
        print(f"❌ {name} 조회 오류: {e}")
        return None


# ========== 시장 지수 조회 ==========
def get_market_indices():
    """주요 시장 지수 조회"""
    indices = {}
    
    try:
        # 한국 지수
        print("📊 한국 지수 조회 중...")
        kospi = yf.Ticker("^KS11")
        kospi_data = kospi.history(period="5d")
        if not kospi_data.empty:
            kospi_price = kospi_data['Close'].iloc[-1]
            kospi_prev = kospi_data['Close'].iloc[-2] if len(kospi_data) > 1 else kospi_price
            kospi_change = kospi_price - kospi_prev
            kospi_rate = (kospi_change / kospi_prev * 100) if kospi_prev else 0
            
            indices['kospi'] = {
                'price': f"{kospi_price:,.2f}",
                'change': f"{kospi_change:+.2f}",
                'rate': f"{kospi_rate:+.2f}"
            }
        
        # 미국 지수
        print("📊 미국 지수 조회 중...")
        sp500 = yf.Ticker("^GSPC")
        sp500_data = sp500.history(period="5d")
        if not sp500_data.empty:
            sp500_price = sp500_data['Close'].iloc[-1]
            sp500_prev = sp500_data['Close'].iloc[-2] if len(sp500_data) > 1 else sp500_price
            sp500_change = sp500_price - sp500_prev
            sp500_rate = (sp500_change / sp500_prev * 100) if sp500_prev else 0
            
            indices['sp500'] = {
                'price': f"{sp500_price:,.2f}",
                'change': f"{sp500_change:+.2f}",
                'rate': f"{sp500_rate:+.2f}"
            }
        
        # 홍콩 항셍지수
        print("📊 홍콩 지수 조회 중...")
        hsi = yf.Ticker("^HSI")
        hsi_data = hsi.history(period="5d")
        if not hsi_data.empty:
            hsi_price = hsi_data['Close'].iloc[-1]
            hsi_prev = hsi_data['Close'].iloc[-2] if len(hsi_data) > 1 else hsi_price
            hsi_change = hsi_price - hsi_prev
            hsi_rate = (hsi_change / hsi_prev * 100) if hsi_prev else 0
            
            indices['hsi'] = {
                'price': f"{hsi_price:,.2f}",
                'change': f"{hsi_change:+.2f}",
                'rate': f"{hsi_rate:+.2f}"
            }
        
    except Exception as e:
        print(f"❌ 지수 조회 오류: {e}")
    
    return indices


# ========== 종합 리포트 생성 ==========
def create_daily_report():
    """일일 글로벌 주식 리포트 생성"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    message = f"🌍 <b>글로벌 주식 정보 리포트</b>\n"
    message += f"⏰ {now}\n"
    message += "="*35 + "\n\n"
    
    # 1. 시장 지수
    indices = get_market_indices()
    
    if 'kospi' in indices:
        message += "🇰🇷 <b>한국 시장</b>\n"
        kospi = indices['kospi']
        emoji = "🔴" if float(kospi['change']) < 0 else "🔵"
        message += f"{emoji} 코스피: {kospi['price']} "
        message += f"({kospi['change']} / {kospi['rate']}%)\n\n"
    
    if 'sp500' in indices:
        message += "🇺🇸 <b>미국 시장</b>\n"
        sp500 = indices['sp500']
        emoji = "🔴" if float(sp500['change']) < 0 else "🔵"
        message += f"{emoji} S&P 500: {sp500['price']} "
        message += f"({sp500['change']} / {sp500['rate']}%)\n\n"
    
    if 'hsi' in indices:
        message += "🇭🇰 <b>홍콩 시장</b>\n"
        hsi = indices['hsi']
        emoji = "🔴" if float(hsi['change']) < 0 else "🔵"
        message += f"{emoji} 항셍지수: {hsi['price']} "
        message += f"({hsi['change']} / {hsi['rate']}%)\n\n"
    
    # 2. 환율
    exchange = get_exchange_rates()
    if exchange:
        message += "💱 <b>환율</b>\n"
        message += f"🇺🇸 USD: {exchange['usd_krw']}원\n"
        message += f"🇯🇵 JPY(100): {exchange['jpy_krw']}원\n"
        message += f"🇭🇰 HKD: {exchange['hkd_krw']}원\n\n"
    
    # 3. 한국 관심 종목
    message += "⭐ <b>한국 관심 종목</b>\n"
    for symbol, name in INTEREST_STOCKS_KR.items():
        stock_info = get_stock_info_with_returns(symbol, name, "KR")
        if stock_info:
            emoji = "🔴" if float(stock_info['change']) < 0 else "🔵"
            message += f"{emoji} <b>{stock_info['name']}</b>: {stock_info['price']}원\n"
            message += f"   일: {stock_info['rate']}% | "
            message += f"주: {stock_info['week_return']}% | "
            message += f"월: {stock_info['month_return']}%\n"
            message += f"   YTD: {stock_info['ytd_return']}% | "
            message += f"년: {stock_info['year_return']}%\n"
        time.sleep(1)
    message += "\n"
    
    # 4. 미국 관심 종목
    message += "⭐ <b>미국 관심 종목</b>\n"
    for symbol, name in INTEREST_STOCKS_US.items():
        stock_info = get_stock_info_with_returns(symbol, name, "US")
        if stock_info:
            emoji = "🔴" if float(stock_info['change']) < 0 else "🔵"
            message += f"{emoji} <b>{stock_info['name']}</b>: ${stock_info['price']}\n"
            message += f"   일: {stock_info['rate']}% | "
            message += f"주: {stock_info['week_return']}% | "
            message += f"월: {stock_info['month_return']}%\n"
            message += f"   YTD: {stock_info['ytd_return']}% | "
            message += f"년: {stock_info['year_return']}%\n"
        time.sleep(1)
    message += "\n"
    
    # 5. 홍콩 관심 종목
    message += "⭐ <b>홍콩 관심 종목</b>\n"
    for symbol, name in INTEREST_STOCKS_HK.items():
        stock_info = get_stock_info_with_returns(symbol, name, "HK")
        if stock_info:
            emoji = "🔴" if float(stock_info['change']) < 0 else "🔵"
            message += f"{emoji} <b>{stock_info['name']}</b>: {stock_info['price']} HKD\n"
            message += f"   일: {stock_info['rate']}% | "
            message += f"주: {stock_info['week_return']}% | "
            message += f"월: {stock_info['month_return']}%\n"
            message += f"   YTD: {stock_info['ytd_return']}% | "
            message += f"년: {stock_info['year_return']}%\n"
        time.sleep(1)
    
    message += "\n" + "="*35
    message += "\n💡 글로벌 투자, 신중하게!"
    message += "\n📊 수익률: 일/주/월/YTD/년"
    
    return message


# ========== 정기 알림 함수 ==========
def send_daily_report():
    """일일 리포트 전송"""
    print(f"📊 리포트 생성 중... {datetime.now()}")
    report = create_daily_report()
    send_telegram_message(report)


# ========== 즉시 테스트 함수 ==========
def test_now():
    """즉시 리포트 전송 (테스트용)"""
    print("🧪 테스트 리포트 전송 중...")
    send_daily_report()


# ========== 스케줄 설정 ==========
def setup_schedule():
    """알림 스케줄 설정"""
    # 한국 장 시작 전 (09:00)
    schedule.every().monday.at("09:00").do(send_daily_report)
    schedule.every().tuesday.at("09:00").do(send_daily_report)
    schedule.every().wednesday.at("09:00").do(send_daily_report)
    schedule.every().thursday.at("09:00").do(send_daily_report)
    schedule.every().friday.at("09:00").do(send_daily_report)
    
    # 한국 장 마감 후 (15:40)
    schedule.every().monday.at("15:40").do(send_daily_report)
    schedule.every().tuesday.at("15:40").do(send_daily_report)
    schedule.every().wednesday.at("15:40").do(send_daily_report)
    schedule.every().thursday.at("15:40").do(send_daily_report)
    schedule.every().friday.at("15:40").do(send_daily_report)
    
    # 미국 장 마감 후 (새벽 06:00)
    schedule.every().tuesday.at("06:00").do(send_daily_report)
    schedule.every().wednesday.at("06:00").do(send_daily_report)
    schedule.every().thursday.at("06:00").do(send_daily_report)
    schedule.every().friday.at("06:00").do(send_daily_report)
    schedule.every().saturday.at("06:00").do(send_daily_report)
    
    print("✅ 스케줄 설정 완료!")
    print("📅 한국 시장: 평일 09:00, 15:40")
    print("📅 미국 시장: 화~토 06:00")


# ========== 메인 실행 ==========
if __name__ == "__main__":
    print("="*50)
    print("🌍 글로벌 주식 정보 텔레그램 봇 (yfinance)")
    print("="*50)
    
    if TELEGRAM_BOT_TOKEN == "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s":
        print("⚠️  TELEGRAM_BOT_TOKEN을 설정해주세요!")
        exit()
    
    if TELEGRAM_CHAT_ID == "417485629":
        print("⚠️  TELEGRAM_CHAT_ID를 설정해주세요!")
        exit()
    
    print("\n테스트 메시지를 지금 보내시겠습니까?")
    print("1. 예 (즉시 테스트)")
    print("2. 아니오 (스케줄만 설정)")
    choice = input("선택 (1 또는 2): ")
    
    if choice == "1":
        test_now()
        print("\n✅ 테스트 메시지를 전송했습니다!")
        print("📱 텔레그램을 확인해주세요.\n")
    
    setup_schedule()
    
    print("\n🤖 봇이 실행 중입니다...")
    print("⏹️  종료하려면 Ctrl+C를 누르세요.\n")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n👋 봇을 종료합니다.")
