import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime
from flask import Flask
from threading import Thread
import gc

# --- Flask 서버 (Render 유지용) ---
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

# 텔레그램으로 관리할 포트폴리오 (메모리 저장 방식)
# 형식: {"AAPL": [평단, 수량], "005930.KS": [평단, 수량]}
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
alerted_stocks = set()
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
        hist = ticker.history(period="2y")
        if len(hist) < 2: return None
        curr = hist['Close'].iloc[-1]
        p_1d = hist['Close'].iloc[-2]
        p_1w = hist['Close'].iloc[-6] if len(hist) >= 6 else hist['Close'].iloc[0]
        p_1m = hist['Close'].iloc[-22] if len(hist) >= 22 else hist['Close'].iloc[0]
        ytd_val = hist.loc[hist.index.date >= datetime(datetime.now().year, 1, 1).date()]
        p_ytd = ytd_val['Close'].iloc[0] if not ytd_val.empty else hist['Close'].iloc[0]
        
        calc = lambda old: ((curr - old) / old * 100)
        return {"price": curr, "1D": calc(p_1d), "1W": calc(p_1w), "1M": calc(p_1m), "YTD": calc(p_ytd)}
    except: return None

# --- 텔레그램 관리 기능 ---

def register_asset(query, chat_id):
    """형식: /등록 종목명(혹은티커) 평단 수량"""
    try:
        parts = query.split()
        name_query = parts[1]
        buy_price = float(parts[2])
        amount = float(parts[3])
        
        # 이름으로 티커 찾기
        symbol = name_query
        for cat in ASSETS_CATEGORIZED.values():
            for s, name in cat.items():
                if name_query in name:
                    symbol = s
                    break
        
        MY_PORTFOLIO[symbol] = [buy_price, amount]
        send_telegram_message(f"✅ <b>등록 완료</b>\n종목: {symbol}\n평단: {buy_price:,.2f}\n수량: {amount:,.2f}", chat_id)
    except:
        send_telegram_message("❌ <b>입력 오류</b>\n형식: <code>/등록 종목명 평단 수량</code>\n(예: /등록 삼성전자 72000 10)", chat_id)

def delete_asset(query, chat_id):
    """형식: /삭제 종목명"""
    try:
        name_query = query.split()[1]
        target = None
        for sym in MY_PORTFOLIO.keys():
            if name_query in sym: target = sym; break
        
        if target in MY_PORTFOLIO:
            del MY_PORTFOLIO[target]
            send_telegram_message(f"🗑 <b>{target}</b> 삭제 완료", chat_id)
        else:
            send_telegram_message("❌ 포트폴리오에 없는 종목입니다.", chat_id)
    except: pass

def check_portfolio(chat_id):
    if not MY_PORTFOLIO:
        send_telegram_message("📝 등록된 포트폴리오가 없습니다.\n<code>/등록</code> 명령어로 추가해 보세요!", chat_id)
        return

    send_telegram_message("💰 <b>수익률 계산 중...</b>", chat_id)
    usd_krw = get_multi_period_returns("KRW=X")
    rate = usd_krw['price'] if usd_krw else 1350
    
    total_buy_krw = 0
    total_curr_krw = 0
    report = "📋 <b>실시간 포트폴리오</b>\n\n"

    for sym, info in MY_PORTFOLIO.items():
        buy_p, amt = info
        data = get_multi_period_returns(sym)
        if not data: continue
        
        is_usd = any(x in sym for x in ["-USD", "=F"]) or (not sym.endswith(".KS") and not sym.endswith(".KQ"))
        buy_krw = (buy_p * amt * rate) if is_usd else (buy_p * amt)
        curr_krw = (data['price'] * amt * rate) if is_usd else (data['price'] * amt)
        p_rate = ((data['price'] - buy_p) / buy_p) * 100
        
        total_buy_krw += buy_krw
        total_curr_krw += curr_krw
        emoji = "🔴" if p_rate > 0 else "🔵"
        report += f"{emoji} <b>{sym}</b>: {p_rate:+.2f}%\n"

    total_p_rate = ((total_curr_krw - total_buy_krw) / total_buy_krw) * 100
    report += f"--------------------\n💰 <b>총 손익: {total_curr_krw - total_buy_krw:+, .0f}원 ({total_p_rate:+.2f}%)</b>"
    send_telegram_message(report, chat_id)

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
                
                if text.startswith('/등록'): register_asset(text, cid)
                elif text.startswith('/삭제'): delete_asset(text, cid)
                elif text in ['포트', '포트폴리오']: check_portfolio(cid)
                elif text in ['/start', '도움말']:
                    msg = ("🤖 <b>명령어 안내</b>\n\n"
                           "1️⃣ <b>등록</b>: <code>/등록 종목명 평단 수량</code>\n"
                           "2️⃣ <b>삭제</b>: <code>/삭제 종목명</code>\n"
                           "3️⃣ <b>조회</b>: <code>포트</code>\n"
                           "4️⃣ <b>검색</b>: <code>/s 티커</code>")
                    send_telegram_message(msg, cid)
    except: pass

# --- 실행부 ---
if __name__ == "__main__":
    keep_alive()
    schedule.every(10).minutes.do(lambda: None) # 모니터링 생략(구조 유지)
    print("🚀 텔레그램 입력형 봇 가동!")
    while True:
        schedule.run_pending()
        handle_commands()
        time.sleep(1)
