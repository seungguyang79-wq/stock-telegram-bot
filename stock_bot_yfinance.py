import os
import yfinance as yf
import requests
import time
import json
from datetime import datetime
from flask import Flask
from threading import Thread

# --- Flask 서버 ---
app = Flask(__name__)
@app.route('/')
def home(): return "Expert Stock Bot is Online! ✅"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    Thread(target=run_server, daemon=True).start()

# --- 설정 ---
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"
DB_FILE = "portfolio.json"

# [티커 변환 사전]
TICKER_DICT = {
    "삼성전자": "005930.KS", "삼성": "005930.KS", "SK하이닉스": "000660.KS", "하이닉스": "000660.KS",
    "현대차": "005380.KS", "네이버": "035420.KS", "카카오": "035720.KS",
    "엔비디아": "NVDA", "테슬라": "TSLA", "애플": "AAPL", "구글": "GOOGL",
    "비트코인": "BTC-USD", "이더리움": "ETH-USD", "금": "GC=F", "은": "SI=F"
}

# [마켓 리포트 구성]
ASSETS_CATEGORIZED = {
    "🌐 지수 및 매크로": {
        "^KS11": "코스피", "^GSPC": "S&P500", "^IXIC": "나스닥", "KRW=X": "환율"
    },
    "🇺🇸 미국 M7": {
        "AAPL": "애플", "NVDA": "엔비", "TSLA": "테슬", "MSFT": "미소"
    },
    "🇰🇷 한국 주요주": {
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스"
    },
    "🪙 자산 및 원자재": { 
        "BTC-USD": "비트코인", "GC=F": "금(Gold)", "SI=F": "은(Silver)" 
    }
}

def load_pf():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_pf(pf_data):
    try:
        with open(DB_FILE, 'w') as f: json.dump(pf_data, f)
    except: pass

MY_PORTFOLIO = load_pf()
last_update_id = 0

def send_msg(text, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except: pass

def get_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        h = ticker.history(period="5d")
        if h.empty: return None
        return {"price": h['Close'].iloc[-1], "1D": ((h['Close'].iloc[-1] - h['Close'].iloc[-2]) / h['Close'].iloc[-2] * 100)}
    except: return None

def find_ticker(query):
    query = query.strip()
    if query in TICKER_DICT: return TICKER_DICT[query]
    return query.upper()

# --- 명령어 함수 ---
def show_help(chat_id):
    msg = (
        "🤖 <b>주식/자산 관리 봇 명령어</b>\n\n"
        "📈 <b>조회 기능</b>\n"
        "• <code>리포트</code> 또는 <code>전체</code> : 글로벌 시장 요약\n"
        "• <code>포트</code> 또는 <code>pf</code> : 내 수익률 확인\n\n"
        "⚙️ <b>관리 기능</b>\n"
        "• <code>/등록 종목명 평단 수량</code>\n"
        "  (예: /등록 삼성전자 72000 10)\n"
        "• <code>/삭제 종목명</code>\n"
        "  (예: /삭제 삼성전자)\n\n"
        "💡 <b>팁</b>: 금, 은, 비트코인도 등록 가능합니다!"
    )
    send_msg(msg, chat_id)

def run_full_report(chat_id):
    send_msg("📊 <b>마켓 리포트 생성 중...</b>", chat_id)
    report = f"🌍 <b>글로벌 요약 ({datetime.now().strftime('%H:%M')})</b>\n\n"
    for cat, stocks in ASSETS_CATEGORIZED.items():
        report += f"<b>[{cat}]</b>\n"
        for sym, name in stocks.items():
            d = get_data(sym)
            if d: report += f"• {name}: {d['1D']:+.2f}%\n"
        report += "\n"
    send_msg(report, chat_id)

def run_portfolio_report(chat_id):
    pf = load_pf()
    if not pf:
        send_msg("📝 등록된 자산이 없습니다. <code>/등록</code>으로 추가하세요.", chat_id)
        return
    send_msg("💰 <b>수익률 계산 중...</b>", chat_id)
    fx = get_data("KRW=X")
    rate = fx['price'] if fx else 1350
    total_buy, total_curr, pf_detail = 0, 0, ""

    for sym, info in pf.items():
        buy_p, amt = info
        d = get_data(sym)
        if not d: continue
        is_usd = any(x in sym for x in ["-USD", "=F"]) or (not sym.endswith(".KS") and not sym.endswith(".KQ"))
        c_price = d['price']
        b_krw = (buy_p * amt * rate) if is_usd else (buy_p * amt)
        c_krw = (c_price * amt * rate) if is_usd else (c_price * amt)
        p_rate = ((c_price - buy_p) / buy_p) * 100
        total_buy += b_krw
        total_curr += c_krw
        emoji = "🔴" if p_rate > 0 else "🔵"
        pf_detail += f"{emoji} <b>{sym}</b>: {p_rate:+.2f}% (현가:{c_price:,.0f})\n"

    total_profit = total_curr - total_buy
    total_rate = (total_profit / total_buy * 100) if total_buy != 0 else 0
    res = f"📋 <b>포트폴리오 현황</b>\n\n{pf_detail}\n💰 <b>총 손익: {total_profit:+, .0f}원 ({total_rate:+.2f}%)</b>"
    send_msg(res, chat_id)

def handle_commands():
    global last_update_id, MY_PORTFOLIO
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": last_update_id + 1, "timeout": 5}, timeout=10)
        for u in r.json().get('result', []):
            last_update_id = u['update_id']
            if 'message' in u and 'text' in u['message']:
                text = u['message']['text'].strip()
                cid = u['message']['chat']['id']
                if text.startswith('/등록'):
                    parts = text.split()
                    if len(parts) == 4:
                        ticker = find_ticker(parts[1])
                        MY_PORTFOLIO[ticker] = [float(parts[2]), float(parts[3])]
                        save_pf(MY_PORTFOLIO)
                        send_msg(f"✅ <b>{ticker}</b> 등록 완료!", cid)
                elif text in ['포트', 'pf']: run_portfolio_report(cid)
                elif text in ['리포트', '전체']: run_full_report(cid)
                elif text.startswith('/삭제'):
                    parts = text.split()
                    if len(parts) == 2:
                        target = find_ticker(parts[1]); del MY_PORTFOLIO[target]
                        save_pf(MY_PORTFOLIO); send_msg(f"🗑 {target} 삭제 완료", cid)
                elif text in ['/help', '도움말', '도움', '/start']: show_help(cid)
    except: pass

if __name__ == "__main__":
    keep_alive()
    MY_PORTFOLIO = load_pf()
    while True:
        handle_commands()
        time.sleep(1)
