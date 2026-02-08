import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime
from flask import Flask
from threading import Thread

# Render 포트 바인딩 해결을 위한 Flask 서버 설정 #
app = Flask('')

@app.route('/')
def home():
return "Bot is running!"

def run_server():
port = int(os.environ.get("PORT", 10000))
app.run(host='0.0.0.0', port=port)

def keep_alive():
t = Thread(target=run_server)
t.daemon = True
t.start()

# 텔레그램 설정#

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "417485629")

INTEREST_STOCKS_KR = {"005930.KS": "삼성전자", "000660.KS": "SK하이닉스"}
INTEREST_STOCKS_US = {"AAPL": "애플", "TSLA": "테슬라", "NVDA": "엔비디아"}

def send_telegram_message(message):
url = f"{TELEGRAM_BOT_TOKEN}/sendMessage"
payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
try:
requests.post(url, data=payload)
except Exception as e:
print(f"Error: {e}")

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
except:
return None

def job():
now = datetime.now().strftime("%Y-%m-%d %H:%M")
report = f"🌍 글로벌 주식 리포트 ({now})\n" + "="*25 + "\n"
for s, n in INTEREST_STOCKS_KR.items():
info = get_stock_info(s, n, "KR")
if info:
report += info + "\n"
for s, n in INTEREST_STOCKS_US.items():
info = get_stock_info(s, n, "US")
if info:
report += info + "\n"
send_telegram_message(report)

if name == "main":
print("🚀 봇 가동 시작...")
keep_alive()
schedule.every().day.at("09:00").do(job)
schedule.every().day.at("15:40").do(job)
send_telegram_message("✅ 봇이 Render 서버에서 성공적으로 실행되었습니다!")
try:
while True:
schedule.run_pending()
time.sleep(60)
except KeyboardInterrupt:
print("종료")
