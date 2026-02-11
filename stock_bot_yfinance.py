import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime
from flask import Flask
from threading import Thread

# 차트 생성은 선택적으로
ENABLE_CHARTS = os.getenv("ENABLE_CHARTS", "false").lower() == "true"

if ENABLE_CHARTS:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import io

# Flask 서버
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()

# 텔레그램 설정
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "417485629")

# 관심 종목
INTEREST_STOCKS_KR = {
    "005930.KS": "삼성전자", 
    "000660.KS": "SK하이닉스"
}

INTEREST_STOCKS_US = {
    "AAPL": "애플", 
    "TSLA": "테슬라", 
    "NVDA": "엔비디아"
}

CRYPTO = {
    "BTC-USD": "비트코인",
    "ETH-USD": "이더리움"
}

PRECIOUS_METALS = {
    "GC=F": "금",
    "SI=F": "은"
}

CURRENCIES = {
    "KRW=X": "달러/원",
    "JPYKRW=X": "100엔/원"
}

def send_telegram_message(message):
    """텔레그램 텍스트 메시지 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print(f"✅ 메시지 전송 성공: {datetime.now()}")
            return True
        else:
            print(f"❌ 메시지 전송 실패: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def send_telegram_photo(image_buffer, caption=""):
    """텔레그램 이미지 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        files = {'photo': ('chart.png', image_buffer, 'image/png')}
        data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            print(f"✅ 이미지 전송 성공: {datetime.now()}")
            return True
        else:
            print(f"❌ 이미지 전송 실패: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def get_stock_info(symbol, name, market="US"):
    """주식 정보 조회"""
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="2d")
        if hist.empty:
            return None
        curr = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else curr
        rate = ((curr - prev) / prev) * 100 if prev else 0
        
        if market == "KR":
            return f"🔹 {name}: {curr:,.0f}원 ({rate:+.2f}%)"
        else:
            return f"🔹 {name}: ${curr:.2f} ({rate:+.2f}%)"
    except Exception as e:
        print(f"❌ {name} 오류: {e}")
        return None

def get_crypto_info(symbol, name):
    """암호화폐 정보 조회"""
    try:
        crypto = yf.Ticker(symbol)
        hist = crypto.history(period="2d")
        if hist.empty:
            return None
        curr = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else curr
        rate = ((curr - prev) / prev) * 100 if prev else 0
        
        return f"₿ {name}: ${curr:,.2f} ({rate:+.2f}%)"
    except Exception as e:
        print(f"❌ {name} 오류: {e}")
        return None

def get_metal_info(symbol, name):
    """귀금속 정보 조회"""
    try:
        metal = yf.Ticker(symbol)
        hist = metal.history(period="2d")
        if hist.empty:
            return None
        curr = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else curr
        rate = ((curr - prev) / prev) * 100 if prev else 0
        
        return f"🪙 {name}: ${curr:,.2f}/oz ({rate:+.2f}%)"
    except Exception as e:
        print(f"❌ {name} 오류: {e}")
        return None

def get_currency_info(symbol, name):
    """환율 정보 조회"""
    try:
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            usd_to_krw = data['usd'].get('krw', 0)
            jpy_rate = data['usd'].get('jpy', 0)
            
            if "KRW" in symbol:
                return f"💱 {name}: {usd_to_krw:,.2f}원"
            elif "JPY" in symbol:
                jpy_krw = (usd_to_krw / jpy_rate) * 100 if jpy_rate else 0
                return f"💱 {name}: {jpy_krw:,.2f}원"
    except Exception as e:
        print(f"❌ 환율 조회 오류: {e}")
        return None

def create_simple_chart():
    """간단한 차트 생성 (메모리 절약)"""
    if not ENABLE_CHARTS:
        return None
    
    try:
        print("📊 차트 생성 중...")
        import matplotlib.pyplot as plt
        import io
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 수익률 계산
        returns = {}
        all_assets = {**INTEREST_STOCKS_US, **CRYPTO}
        
        for symbol, name in all_assets.items():
            try:
                asset = yf.Ticker(symbol)
                hist = asset.history(period="1mo")
                if len(hist) >= 2:
                    first = hist['Close'].iloc[0]
                    last = hist['Close'].iloc[-1]
                    ret = ((last - first) / first) * 100
                    returns[name] = ret
            except:
                pass
        
        if returns:
            names = list(returns.keys())
            values = list(returns.values())
            colors = ['#2ecc71' if v > 0 else '#e74c3c' for v in values]
            
            ax.barh(names, values, color=colors, alpha=0.7)
            ax.set_xlabel('Return (%)', fontsize=12)
            ax.set_title('30-Day Returns', fontsize=14, fontweight='bold')
            ax.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
            ax.grid(True, alpha=0.3, axis='x')
            
            for i, (name, value) in enumerate(zip(names, values)):
                ax.text(value, i, f' {value:+.1f}%', va='center', fontsize=9)
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close('all')  # 메모리 해제
        
        print("✅ 차트 생성 완료")
        return buf
        
    except Exception as e:
        print(f"❌ 차트 생성 오류: {e}")
        return None

def job():
    """정기 리포트 생성 및 전송"""
    print(f"📊 리포트 생성 시작: {datetime.now()}")
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    report = f"🌍 <b>글로벌 투자 리포트</b> ({now})\n" + "="*30 + "\n\n"
    
    # 1. 한국 주식
    report += "🇰🇷 <b>한국 주식</b>\n"
    for s, n in INTEREST_STOCKS_KR.items():
        info = get_stock_info(s, n, "KR")
        if info:
            report += info + "\n"
        time.sleep(0.3)
    
    # 2. 미국 주식
    report += "\n🇺🇸 <b>미국 주식</b>\n"
    for s, n in INTEREST_STOCKS_US.items():
        info = get_stock_info(s, n, "US")
        if info:
            report += info + "\n"
        time.sleep(0.3)
    
    # 3. 암호화폐
    report += "\n💎 <b>암호화폐</b>\n"
    for s, n in CRYPTO.items():
        info = get_crypto_info(s, n)
        if info:
            report += info + "\n"
        time.sleep(0.3)
    
    # 4. 귀금속
    report += "\n🏆 <b>귀금속</b>\n"
    for s, n in PRECIOUS_METALS.items():
        info = get_metal_info(s, n)
        if info:
            report += info + "\n"
        time.sleep(0.3)
    
    # 5. 환율
    report += "\n💱 <b>환율</b>\n"
    for s, n in CURRENCIES.items():
        info = get_currency_info(s, n)
        if info:
            report += info + "\n"
        time.sleep(0.3)
    
    report += "\n" + "="*30
    report += "\n💡 <i>현명한 투자 하세요!</i>"
    
    # 텍스트 리포트 전송
    if send_telegram_message(report):
        print("✅ 텍스트 리포트 전송 완료")
    
    # 차트 전송 (활성화된 경우에만)
    if ENABLE_CHARTS:
        time.sleep(2)
        chart = create_simple_chart()
        if chart:
            send_telegram_photo(chart, caption="📊 30일 수익률 비교")
    
    print(f"✅ 리포트 작업 완료: {datetime.now()}")

if __name__ == "__main__":
    print("="*50)
    print("🚀 봇 가동 시작...")
    print(f"차트 기능: {'활성화' if ENABLE_CHARTS else '비활성화'}")
    print("="*50)
    
    # Flask 서버 시작
    keep_alive()
    
    # 스케줄 설정
    schedule.every().day.at("09:00").do(job)
    schedule.every().day.at("15:40").do(job)
    
    # 시작 메시지
    chart_msg = " (차트 포함)" if ENABLE_CHARTS else ""
    send_telegram_message(f"✅ 봇이 Render 서버에서 성공적으로 실행되었습니다{chart_msg}!\n🔔 매일 09:00, 15:40에 리포트를 보내드립니다.")
    
    print("🤖 봇이 실행 중입니다...")
    print("⏰ 다음 알림: 09:00, 15:40")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n👋 봇 종료")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        # 오류 발생 시 텔레그램으로 알림
        send_telegram_message(f"⚠️ 봇 오류 발생: {str(e)}")
