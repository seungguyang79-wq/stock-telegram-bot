import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime
from flask import Flask
from threading import Thread

# Render 포트 바인딩 해결을 위한 Flask 서버 설정
app = Flask(__name__)  # ← 수정: '' → __name__

@app.route('/')
def home():
    return "Bot is running!"  # ← 수정: 들여쓰기

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

INTEREST_STOCKS_KR = {"005930.KS": "삼성전자", "000660.KS": "SK하이닉스"}
INTEREST_STOCKS_US = {"AAPL": "애플", "TSLA": "테슬라", "NVDA": "엔비디아"}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"  # ← 수정: URL 완성
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
        print(f"✅ 메시지 전송 성공: {datetime.now()}")
    except Exception as e:
        print(f"❌ Error: {e}")

def get_stock_info(symbol, name, market="US"):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="2d")
        if hist.empty:
            return None
        curr = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2]
        rate = ((curr - prev) / prev) * 100
        fmt = "{:,.0f}" if market == "KR" else "{:.2f}"
        unit = "원" if market == "KR" else "USD"
        return f"🔹 {name}: {fmt.format(curr)}{unit} ({rate:+.2f}%)"
    except Exception as e:
        print(f"❌ {name} 오류: {e}")
        return None

def job():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    report = f"🌍 글로벌 주식 리포트 ({now})\n" + "="*25 + "\n\n"
    
    report += "🇰🇷 한국 주식\n"
    for s, n in INTEREST_STOCKS_KR.items():
        info = get_stock_info(s, n, "KR")
        if info:
            report += info + "\n"
    
    report += "\n🇺🇸 미국 주식\n"
    for s, n in INTEREST_STOCKS_US.items():
        info = get_stock_info(s, n, "US")
        if info:
            report += info + "\n"
    
    send_telegram_message(report)

if __name__ == "__main__":  # ← 수정: name → __name__
    print("🚀 봇 가동 시작...")
    
    # Flask 서버 시작
    keep_alive()
    
    # 스케줄 설정
    schedule.every().day.at("09:00").do(job)
    schedule.every().day.at("15:40").do(job)
    
    # 시작 메시지
    send_telegram_message("✅ 봇이 Render 서버에서 성공적으로 실행되었습니다!")
    
    print("🤖 봇이 실행 중입니다...")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("👋 봇 종료")
