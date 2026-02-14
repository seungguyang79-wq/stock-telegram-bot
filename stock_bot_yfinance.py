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
def home(): return "Fast Stock Bot is Online! ✅"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    Thread(target=run_server, daemon=True).start()

# --- 설정 및 데이터 ---
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"
DB_FILE = "portfolio.json"

def load_pf():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_pf(pf_data):
    with open(DB_FILE, 'w') as f: json.dump(pf_data, f)

MY_PORTFOLIO = load_pf()

# --- 핵심 함수 (속도 최적화) ---
def send_msg(text, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except: pass

def get_fast_data(symbol):
    """데이터 호출을 최소화하여 속도 향상"""
    try:
        ticker = yf.Ticker(symbol)
        # 1년치 대신 1달치만 가져와서 속도 개선 (YTD는 별도 처리 가능 시 시도)
        h = ticker.history(period="1mo") 
        if h.empty: return None
        curr = h['Close'].iloc[-1]
        prev = h['Close'].iloc[-2]
        return {"price": curr, "1D": ((curr - prev) / prev * 100)}
    except: return None

def run_portfolio_report(chat_id):
    pf = load_pf()
    if not pf:
        send_msg("📝 등록된 종목이 없습니다.", chat_id)
        return

    send_msg("⏳ <b>데이터 분석 중... (약 3~5초 소요)</b>", chat_id)
    
    total_buy_krw = 0
    total_curr_krw = 0
    pf_detail = ""
    
    # 환율 정보 (실패 시 기본값)
    rate = 1350
    fx = get_fast_data("KRW=X")
    if fx: rate = fx['price']

    for sym, info in pf.items():
        buy_p, amt = info
        data = get_fast_data(sym)
        if not data: continue
        
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
        send_msg("❌ 데이터를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.", chat_id)
        return

    total_profit = total_curr_krw - total_buy_krw
    total_rate = (total_profit / total_buy_krw * 100) if total_buy_krw != 0 else 0
    
    res = f"📋 <b>수익률 리포트</b>\n\n{pf_detail}\n"
    res += f"💰 <b>총 손익: {total_profit:+, .0f}원 ({total_rate:+.2f}%)</b>"
    send_msg(res, chat_id)

# 명령어 핸들러는 이전과 동일... (생략된 부분은 위 구조 유지)
def handle_commands():
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": last_update_id + 1, "timeout": 5}, timeout=10)
        for u in r.json().get('result', []):
            last_update_id = u['update_id']
            if 'message' in u and 'text' in u['message']:
                text = u['message']['text'].strip()
                cid = u['message']['chat']['id']
                if text.startswith('/등록'):
                    p = text.split()
                    if len(p) == 4:
                        MY_PORTFOLIO[p[1]] = [float(p[2]), float(p[3])] # 간단화를 위해 입력값 그대로 저장
                        save_pf(MY_PORTFOLIO)
                        send_msg(f"✅ {p[1]} 등록 완료!", cid)
                elif text in ['포트', 'pf']: run_portfolio_report(cid)
    except: pass

if __name__ == "__main__":
    keep_alive()
    last_update_id = 0
    while True:
        handle_commands()
        time.sleep(1)
