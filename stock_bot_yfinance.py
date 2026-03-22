import os
import yfinance as yf
import requests
import time
import json
from datetime import datetime
from flask import Flask
from threading import Thread

# --- Flask 서버 (Render 유지용) ---
app = Flask(__name__)
@app.route('/')
def home(): return "David-Catalyst Bot: Final & Persistent! ✅"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    Thread(target=run_server, daemon=True).start()

# --- 설정 및 데이터베이스 --
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"
DB_FILE = "portfolio.json"

# [지능형 티커 변환 사전]
TICKER_DICT = {
    "삼성전자": "005930.KS", "삼성": "005930.KS", "SAMSUNG": "005930.KS",
    "네이버": "035420.KS", "NAVER": "035420.KS",
    "SK하이닉스": "000660.KS", "하이닉스": "000660.KS",
    "엔비디아": "NVDA", "NVIDIA": "NVDA", "NVDA": "NVDA",
    "테슬라": "TSLA", "TESLA": "TSLA", "금": "GC=F", "은": "SI=F"
}

# [마켓 리포트 구성]
ASSETS_CATEGORIZED = {
    "🌐 지수 및 매크로": {"^KS11": "코스피", "^GSPC": "S&P500", "^IXIC": "나스닥", "KRW=X": "환율"},
    "🇺🇸 미국 M7": {"AAPL": "애플", "NVDA": "엔비", "TSLA": "테슬", "MSFT": "미소"},
    "🇰🇷 한국 주요주": {"005930.KS": "삼성전자", "035420.KS": "네이버", "000660.KS": "하이닉스"},
    "🪙 자산 및 원자재": {"BTC-USD": "비트코인", "GC=F": "금(Gold)", "SI=F": "은(Silver)"}
}

# --- 데이터 관리 (고정 데이터 포함) ---
def load_pf():
    # 배포 시마다 사라지지 않게 하는 기본 데이터
    default_pf = {
        "005930.KS": [137600.0, 32.0],  # 삼성전자
        "035420.KS": [300059.0, 53.0],  # 네이버
        "NVDA": [51.6, 236.0]           # 엔비디아
    
    }
    
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                data = json.load(f)
                return data if data else default_pf
        except: return default_pf
    return default_pf

def save_pf(pf_data):
    try:
        with open(DB_FILE, 'w') as f: json.dump(pf_data, f)
    except: pass

MY_PORTFOLIO = load_pf()
last_update_id = 0

# --- 핵심 로직 ---
def get_trend_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        h = ticker.history(period="2mo")
        if len(h) < 2: return None
        curr = h['Close'].iloc[-1]
        d1 = ((curr - h['Close'].iloc[-2]) / h['Close'].iloc[-2]) * 100
        w1 = ((curr - h['Close'].iloc[-6]) / h['Close'].iloc[-6]) * 100 if len(h) >= 6 else 0
        m1 = ((curr - h['Close'].iloc[-21]) / h['Close'].iloc[-21]) * 100 if len(h) >= 21 else 0
        return {"price": curr, "1D": d1, "1W": w1, "1M": m1}
    except: return None

def send_msg(text, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=20)
    except: pass

def find_ticker(query):
    q = query.strip().upper()
    return TICKER_DICT.get(q, q)

def run_portfolio_report(cid):
    pf = load_pf()
    send_msg("⏳ <b>수익률을 정밀 계산 중입니다...</b>", cid)
    try:
        fx_data = yf.Ticker("KRW=X").history(period="1d")
        fx = fx_data['Close'].iloc[-1] if not fx_data.empty else 1350
        
        total_buy, total_curr, pf_detail = 0, 0, ""

        for sym, info in pf.items():
            buy_p, amt = info
            d = get_trend_data(sym)
            if not d: continue
            
            is_usd = any(x in sym for x in ["-USD", "=F"]) or (not sym.endswith(".KS") and not sym.endswith(".KQ"))
            c_price = d['price']
            b_krw = (buy_p * amt * fx) if is_usd else (buy_p * amt)
            c_krw = (c_price * amt * fx) if is_usd else (c_price * amt)
            p_rate = ((c_price - buy_p) / buy_p) * 100
            
            total_buy += b_krw
            total_curr += c_krw
            emoji = "📈" if p_rate > 0 else "📉"
            pf_detail += f"{emoji} <b>{sym}</b>: {p_rate:+.2f}% (현가:{c_price:,.0f})\n"

        total_profit = total_curr - total_buy
        total_rate = (total_profit / total_buy * 100) if total_buy != 0 else 0
        res = f"📋 <b>포트폴리오 현황</b>\n\n{pf_detail}\n💰 <b>총 손익: {total_profit:+,.0f}원 ({total_rate:+.2f}%)</b>"
        send_msg(res, cid)
    except Exception as e:
        send_msg(f"❗ 오류 발생: {str(e)}", cid)

def handle_commands():
    global last_update_id, MY_PORTFOLIO
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": last_update_id + 1, "timeout": 5}, timeout=10)
        for u in r.json().get('result', []):
            last_update_id = u['update_id']
            if 'message' in u and 'text' in u['message']:
                text = u['message']['text'].strip()
                cid = str(u['message']['chat']['id'])
                
                if text.startswith('/등록'):
                    parts = text.split()
                    if len(parts) == 4:
                        ticker = find_ticker(parts[1])
                        MY_PORTFOLIO[ticker] = [float(parts[2]), float(parts[3])]
                        save_pf(MY_PORTFOLIO)
                        send_msg(f"✅ <b>{ticker}</b> 등록 완료!", cid)
                elif text in ['포트', 'pf']: run_portfolio_report(cid)
                elif text in ['리포트', '전체']:
                    send_msg("📊 <b>마켓 리포트 분석 중...</b>", cid)
                    report = f"🌍 <b>글로벌 요약</b>\n<code>(일간 / 주간 / 월간)</code>\n\n"
                    for cat, stocks in ASSETS_CATEGORIZED.items():
                        report += f"<b>[{cat}]</b>\n"
                        for sym, name in stocks.items():
                            d = get_trend_data(sym)
                            if d: report += f"• {name}: {d['1D']:+.1f}% / {d['1W']:+.1f}% / {d['1M']:+.1f}%\n"
                        report += "\n"
                    send_msg(report, cid)
                elif text.startswith('/삭제'):
                    parts = text.split()
                    if len(parts) == 2:
                        target = find_ticker(parts[1])
                        if target in MY_PORTFOLIO:
                            del MY_PORTFOLIO[target]; save_pf(MY_PORTFOLIO)
                            send_msg(f"🗑 {target} 삭제 완료", cid)
                elif text in ['도움말', '/help']:
                    send_msg("🤖 <b>명령어</b>\n• 포트: 내 자산 확인\n• 리포트: 시장 현황\n• /등록 종목 평단 수량\n• /삭제 종목명", cid)
    except: pass

if __name__ == "__main__":
    keep_alive()
    MY_PORTFOLIO = load_pf()
    while True:
        handle_commands()
        time.sleep(1)
