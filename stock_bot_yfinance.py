import os
import yfinance as yf
import requests
import time
import json
from datetime import datetime
from flask import Flask
from threading import Thread

app = Flask(__name__)
@app.route('/')
def home(): return "Enhanced Stock Bot is Online! ✅"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    Thread(target=run_server, daemon=True).start()

# --- 설정 및 데이터 ---
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"
DB_FILE = "portfolio.json"

# [중요] 한글 이름과 티커 매핑 데이터 (검색용)
TICKER_MAP = {
    "삼성전자": "005930.KS", "삼성": "005930.KS",
    "SK하이닉스": "000660.KS", "하이닉스": "000660.KS",
    "현대차": "005380.KS", "네이버": "035420.KS", "카카오": "035720.KS",
    "엔비디아": "NVDA", "테슬라": "TSLA", "애플": "AAPL", "구글": "GOOGL",
    "아마존": "AMZN", "마이크로소프트": "MSFT", "메타": "META",
    "비트코인": "BTC-USD", "이더리움": "ETH-USD"
}

def load_pf():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_pf(pf_data):
    with open(DB_FILE, 'w') as f: json.dump(pf_data, f)

def send_msg(text, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except: pass

# 티커 변환 함수 강화
def convert_to_ticker(name):
    name = name.strip()
    # 1. 매핑 테이블에서 확인
    if name in TICKER_MAP:
        return TICKER_MAP[name]
    # 2. 직접 티커 입력 시 (예: NVDA, 005930.KS) 그대로 반환
    return name.upper()

def get_fast_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        # 속도를 위해 5일치만 가져옴
        h = ticker.history(period="5d") 
        if h.empty: return None
        return {"price": h['Close'].iloc[-1]}
    except: return None

def run_portfolio_report(chat_id):
    pf = load_pf()
    if not pf:
        send_msg("📝 등록된 종목이 없습니다.", chat_id)
        return

    send_msg("⏳ <b>데이터를 불러오는 중입니다...</b>", chat_id)
    
    total_buy_krw = 0
    total_curr_krw = 0
    pf_detail = ""
    rate = 1350 # 환율 기본값
    
    fx = get_fast_data("KRW=X")
    if fx: rate = fx['price']

    for sym, info in pf.items():
        buy_p, amt = info
        data = get_fast_data(sym)
        if not data:
            pf_detail += f"⚠️ <b>{sym}</b>: 데이터 로드 실패\n"
            continue
        
        is_usd = any(x in sym for x in ["-USD", "=F"]) or (not sym.endswith(".KS") and not sym.endswith(".KQ"))
        c_price = data['price']
        
        b_krw = (buy_p * amt * rate) if is_usd else (buy_p * amt)
        c_krw = (c_price * amt * rate) if is_usd else (c_price * amt)
        p_rate = ((c_price - buy_p) / buy_p) * 100
        
        total_buy_krw += b_krw
        total_curr_krw += c_krw
        emoji = "🔴" if p_rate > 0 else "🔵"
        pf_detail += f"{emoji} <b>{sym}</b>: {p_rate:+.2f}%\n"

    if not pf_detail:
        send_msg("❌ 모든 종목의 데이터를 가져오지 못했습니다.", chat_id)
        return

    total_profit = total_curr_krw - total_buy_krw
    total_rate = (total_profit / total_buy_krw * 100) if total_buy_krw != 0 else 0
    
    res = f"📋 <b>수익률 리포트</b>\n\n{pf_detail}\n"
    res += f"💰 <b>총 손익: {total_profit:+, .0f}원 ({total_rate:+.2f}%)</b>"
    send_msg(res, chat_id)

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
                    p = text.split()
                    if len(p) == 4:
                        ticker = convert_to_ticker(p[1])
                        MY_PORTFOLIO[ticker] = [float(p[2]), float(p[3])]
                        save_pf(MY_PORTFOLIO)
                        send_msg(f"✅ <b>{ticker}</b> 등록 완료!", cid)
                elif text in ['포트', 'pf']:
                    run_portfolio_report(cid)
    except: pass

if __name__ == "__main__":
    keep_alive()
    last_update_id = 0
    MY_PORTFOLIO = load_pf()
    while True:
        handle_commands()
        time.sleep(1)
