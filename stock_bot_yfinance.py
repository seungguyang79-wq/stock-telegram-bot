import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime
from flask import Flask
from threading import Thread
import gc

app = Flask(__name__)
@app.route('/')
def home(): return "Interactive Portfolio Bot is Online! ✅"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    Thread(target=run_server, daemon=True).start()

# --- 설정 및 데이터 ---
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"

# 메모리 기반 포트폴리오 (서버 재시작 전까지 유지)
MY_PORTFOLIO = {}

ASSETS_CATEGORIZED = {
    "🌐 지수 및 매크로": {
        "^KS11": "코스피", "^KQ11": "코스닥", "^GSPC": "S&P500", "^IXIC": "나스닥",
        "KRW=X": "원/달러 환율", "^VIX": "공포지수(VIX)", "^TNX": "미 10년물 금리"
    },
    "🇺🇸 미국 M7": {
        "AAPL": "애플", "MSFT": "마이크로소프트", "GOOGL": "구글", "AMZN": "아마존", 
        "NVDA": "엔비디아", "META": "메타", "TSLA": "테슬라"
    },
    "🇰🇷 한국 주요주": {
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "005380.KS": "현대차"
    }
}

last_update_id = 0
ALERT_THRESHOLD = 5.0 

# --- 핵심 함수 ---

def send_telegram_message(text, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=20)
    except: pass

def get_multi_period_returns(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y") # YTD 계산을 위해 1년치만 로드 (메모리 절약)
        if len(hist) < 2: return None
        curr = hist['Close'].iloc[-1]
        p_1d = hist['Close'].iloc[-2]
        
        # 기간별 변동률 계산
        calc = lambda old: ((curr - old) / old * 100)
        return {"price": curr, "1D": calc(p_1d)}
    except: return None

# --- 종목 검색 기능 (한글 이름 대응) ---
def find_ticker(query):
    query_clean = query.strip().upper()
    # 1. 카테고리 리스트에서 한글 이름으로 찾기
    for cat in ASSETS_CATEGORIZED.values():
        for sym, name in cat.items():
            if query in name: return sym
    # 2. 아니면 입력값 그대로 (티커라고 가정)
    return query_clean

def check_portfolio(chat_id):
    if not MY_PORTFOLIO:
        send_telegram_message("📝 등록된 포트폴리오가 없습니다.\n<code>/등록 삼성전자 13900 30</code> 형식으로 추가해 보세요!", chat_id)
        return

    send_telegram_message("💰 <b>수익률을 실시간 계산 중입니다...</b>", chat_id)
    usd_krw_data = get_multi_period_returns("KRW=X")
    rate = usd_krw_data['price'] if usd_krw_data else 1350
    
    total_buy_krw = 0
    total_curr_krw = 0
    report = "📋 <b>포트폴리오 실시간 수익 현황</b>\n\n"

    for sym, info in MY_PORTFOLIO.items():
        buy_p, amt = info
        data = get_multi_period_returns(sym)
        if not data: continue
        
        is_usd = any(x in sym for x in ["-USD", "=F"]) or (not sym.endswith(".KS") and not sym.endswith(".KQ"))
        curr_price = data['price']
        
        item_buy_krw = (buy_p * amt * rate) if is_usd else (buy_p * amt)
        item_curr_krw = (curr_price * amt * rate) if is_usd else (curr_price * amt)
        p_rate = ((curr_price - buy_p) / buy_p) * 100
        
        total_buy_krw += item_buy_krw
        total_curr_krw += item_curr_krw
        
        emoji = "📈" if p_rate > 0 else "📉"
        report += f"{emoji} <b>{sym}</b>\n   수익률: {p_rate:+.2f}%\n   현재가: {curr_price:,.2f} ({'USD' if is_usd else 'KRW'})\n\n"

    total_p_rate = ((total_curr_krw - total_buy_krw) / total_buy_krw) * 100
    report += "--------------------\n"
    report += f"💰 <b>총 손익: {total_curr_krw - total_buy_krw:+, .0f}원\n평균 수익률: {total_p_rate:+.2f}%</b>"
    send_telegram_message(report, chat_id)

def handle_commands():
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": last_update_id + 1, "timeout": 5}, timeout=10)
        updates = r.json().get('result', [])
        for u in updates:
            last_update_id = u['update_id']
            if 'message' in u and 'text' in u['message']:
                text = u['message']['text'].strip()
                cid = u['message']['chat']['id']
                
                if text.startswith('/등록'):
                    try:
                        parts = text.split()
                        ticker = find_ticker(parts[1])
                        MY_PORTFOLIO[ticker] = [float(parts[2]), float(parts[3])]
                        send_telegram_message(f"✅ <b>등록 완료</b>\n종목: {ticker}\n평단: {float(parts[2]):,.2f}\n수량: {float(parts[3]):,.2f}", cid)
                    except: send_telegram_message("❌ 형식 오류! 예: /등록 삼성전자 72000 10", cid)
                
                elif text.startswith('/s '):
                    ticker = find_ticker(text[3:])
                    data = get_multi_period_returns(ticker)
                    if data:
                        send_telegram_message(f"🔍 <b>{ticker} 검색 결과</b>\n현재가: {data['price']:,.2f}\n전일대비: {data['1D']:+.2f}%", cid)
                    else: send_telegram_message("❌ 데이터를 찾을 수 없습니다.", cid)
                
                elif text in ['포트', '포트폴리오']: check_portfolio(cid)
                elif text in ['리포트', '전체']:
                    send_telegram_message("📊 전체 리포트 기능을 실행합니다...", cid)
                    # 기존 리포트 로직 호출...
    except: pass

if __name__ == "__main__":
    keep_alive()
    print("🚀 봇 재가동 시작...")
    while True:
        handle_commands()
        time.sleep(1)
