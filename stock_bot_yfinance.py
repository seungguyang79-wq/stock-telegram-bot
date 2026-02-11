import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime
from flask import Flask
from threading import Thread
import io
import gc

# matplotlib 설정
import matplotlib
matplotlib.use('Agg')  # 서버 환경(GUI 없음)용 설정
import matplotlib.pyplot as plt

# Flask 서버 설정 (Render 등 호스팅 서비스용)
app = Flask(__name__)

@app.route('/')
def home():
    return "Stock Bot is Running! ✅"

@app.route('/health')
def health():
    return "OK", 200

def run_server():
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask 서버 시작: 포트 {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    t = Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(2)

# 텔레그램 설정
# 주의: 토큰은 환경변수(Environment Variables)로 관리하는 것이 보안상 안전합니다.
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"

# 마지막으로 처리한 메시지 ID
last_update_id = 0

# 관심 종목 (차트 깨짐 방지를 위해 영문 이름 병기)
STOCKS_KR = {"005930.KS": "Samsung", "000660.KS": "Hynix"}
STOCKS_US = {"AAPL": "Apple", "TSLA": "Tesla", "NVDA": "Nvidia"}
CRYPTO = {"BTC-USD": "Bitcoin", "ETH-USD": "Ethereum"}
METALS = {"GC=F": "Gold", "SI=F": "Silver"}

def send_message(text, chat_id=None):
    if chat_id is None: chat_id = TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"❌ 전송 오류: {e}")
        return False

def send_photo(image_buffer, caption="", chat_id=None):
    if chat_id is None: chat_id = TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        files = {'photo': ('chart.png', image_buffer, 'image/png')}
        data = {'chat_id': chat_id, 'caption': caption}
        response = requests.post(url, files=files, data=data, timeout=30)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ 이미지 전송 오류: {e}")
        return False

def get_price(symbol, name, market):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        if hist.empty: return None
        
        curr = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else curr
        change = ((curr - prev) / prev * 100) if prev else 0
        
        if market == "KR":
            return {'text': f"🔹 {name}: {curr:,.0f}원 ({change:+.1f}%)", 
                    'detail': f"📊 <b>{name}</b>\n💰 현재가: {curr:,.0f}원\n📈 변동: {change:+.2f}%"}
        else:
            unit = "$" if market != "METAL" else "$/oz"
            return {'text': f"🔹 {name}: {unit}{curr:,.2f} ({change:+.1f}%)", 
                    'detail': f"📊 <b>{name}</b>\n💰 현재가: {unit}{curr:,.2f}\n📈 변동: {change:+.2f}%"}
    except:
        return None

def get_exchange_rate():
    try:
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
        r = requests.get(url, timeout=10)
        data = r.json()
        usd_krw = data['usd'].get('krw', 0)
        return f"💱 <b>환율 정보</b>\n🇺🇸 USD/KRW: {usd_krw:,.2f}원"
    except:
        return None

def create_chart():
    """30일 수익률 차트 생성 (영문 표기)"""
    try:
        returns = {}
        all_assets = {**STOCKS_KR, **STOCKS_US, **CRYPTO, **METALS}
        for symbol, name in all_assets.items():
            hist = yf.Ticker(symbol).history(period="1mo")
            if len(hist) >= 2:
                ret = ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                returns[name] = ret
            time.sleep(0.1)

        fig, ax = plt.subplots(figsize=(10, 7))
        names, values = list(returns.keys()), list(returns.values())
        colors = ['#2ecc71' if v > 0 else '#e74c3c' for v in values]
        ax.barh(names, values, color=colors)
        ax.set_title('30-Day Asset Returns (%)', fontsize=14)
        ax.axvline(0, color='black', lw=1)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close('all')
        gc.collect()
        return buf
    except Exception as e:
        print(f"Chart Error: {e}")
        return None

def create_full_report():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"🌍 <b>글로벌 투자 리포트</b>\n⏰ {now}\n{'='*25}\n"
    
    sections = [("🇰🇷 KR Stock", STOCKS_KR, "KR"), ("🇺🇸 US Stock", STOCKS_US, "US"), 
                ("💎 Crypto", CRYPTO, "CRYPTO"), ("🏆 Metal", METALS, "METAL")]
    
    for title, mapping, m_type in sections:
        msg += f"\n<b>{title}</b>\n"
        for sym, nam in mapping.items():
            info = get_price(sym, nam, m_type)
            if info: msg += info['text'] + "\n"
    
    ex = get_exchange_rate()
    if ex: msg += f"\n{ex}"
    return msg

def handle_command(text, chat_id):
    text = text.lower().strip()
    
    if text in ['/start', '도움말', 'help']:
        msg = "🤖 <b>명령어 안내</b>\n• 전체: 실시간 리포트\n• 차트: 30일 수익률 비교\n• 환율: 현재 환율\n• 삼성/애플/비트: 상세 정보"
        send_message(msg, chat_id)
    elif text in ['전체', '리포트']:
        send_message("📊 리포트를 생성하고 있습니다...", chat_id)
        send_message(create_full_report(), chat_id)
    elif text in ['차트', 'chart']:
        send_message("📈 차트 분석 중... (잠시만 기다려주세요)", chat_id)
        chart = create_chart()
        if chart: send_photo(chart, "📊 30일 수익률 분석", chat_id)
        else: send_message("❌ 차트 생성 실패", chat_id)
    elif '삼성' in text:
        info = get_price("005930.KS", "삼성전자", "KR")
        if info: send_message(info['detail'], chat_id)
    elif '비트' in text:
        info = get_price("BTC-USD", "Bitcoin", "CRYPTO")
        if info: send_message(info['detail'], chat_id)
    # 필요한 다른 조건들도 위와 같은 방식으로 추가 가능

def check_messages():
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": last_update_id + 1, "timeout": 10}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            for update in data.get('result', []):
                last_update_id = update['update_id']
                if 'message' in update and 'text' in update['message']:
                    handle_command(update['message']['text'], update['message']['chat']['id'])
    except Exception as e:
        print(f"Polling Error: {e}")

def scheduled_job():
    """정기 작업 함수 (이름 수정됨)"""
    print(f"⏰ 정기 보고서 전송 시작")
    msg = create_full_report()
    send_message(msg)

if __name__ == "__main__":
    print("🚀 Stock Bot Starting...")
    keep_alive() # Flask 서버 시작
    
    # 스케줄 등록 (job -> scheduled_job으로 수정)
    times = ["09:00", "11:30", "13:30", "15:40", "22:30"]
    for t in times:
        schedule.every().day.at(t).do(scheduled_job)
    
    send_message("✅ <b>주식 봇 가동 시작</b>\n자동 보고 시간: " + ", ".join(times))
    
    try:
        while True:
            schedule.run_pending()
            check_messages()
            time.sleep(5)
    except KeyboardInterrupt:
        print("Bot Stopped")
