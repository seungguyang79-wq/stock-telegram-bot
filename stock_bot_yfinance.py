import os
import yfinance as yf
import requests
import schedule
import time
import json
from datetime import datetime
from flask import Flask
from threading import Thread

app = Flask(__name__)
@app.route('/')
def home(): return "Global Multi-Asset Bot with Persistence is Online! ✅"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    Thread(target=run_server, daemon=True).start()

# --- 설정 및 데이터 ---
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"
DB_FILE = "portfolio.json"

# 포트폴리오 로드/저장 함수
def load_pf():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f: return json.load(f)
    return {}

def save_pf(pf_data):
    with open(DB_FILE, 'w') as f: json.dump(pf_data, f)

MY_PORTFOLIO = load_pf()

ASSETS_CATEGORIZED = {
    "🌐 지수 및 매크로": {
        "^KS11": "코스피", "^KQ11": "코스닥", "^GSPC": "S&P500", "^IXIC": "나스닥",
        "^HSI": "항셍", "KRW=X": "환율", "^VIX": "VIX", "^TNX": "10년금리"
    },
    "🇺🇸 미국 M7": {
        "AAPL": "애플", "MSFT": "미소", "GOOGL": "구글", "AMZN": "아마존", 
        "NVDA": "엔비", "META": "메타", "TSLA": "테슬"
    },
    "🇰🇷 한국 주요주": {
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "005380.KS": "현대차", 
        "035420.KS": "NAVER", "035720.KS": "카카오"
    },
    "🇭🇰 홍콩/중국 M7+": {
        "0700.HK": "텐센트", "9988.HK": "알리바바", "3690.HK": "메이투안", "1810.HK": "샤오미"
    },
    "🪙 자산": { "BTC-USD": "비트코인", "ETH-USD": "이더리움", "GC=F": "금" }
}

last_update_id = 0

# --- 공통 함수 ---
def send_msg(text, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=20)
    except: pass

def get_rich_data(symbol):
    try:
        t = yf.Ticker(symbol)
        h = t.history(period="1y") # YTD 계산을 위해 1년 데이터 로드
        if h.empty or len(h) < 2: return None
        
        curr = h['Close'].iloc[-1]
        
        def calc_ret(prev_idx):
            if len(h) >= abs(prev_idx):
                old = h['Close'].iloc[prev_idx]
                return ((curr - old) / old * 100)
            return 0.0

        # YTD 계산
        ytd_data = h.loc[h.index.year == datetime.now().year]
        p_ytd = ytd_data['Close'].iloc[0] if not ytd_data.empty else h['Close'].iloc[0]
        ytd_ret = ((curr - p_ytd) / p_ytd * 100)

        return {
            "price": curr,
            "1D": calc_ret(-2),
            "1W": calc_ret(-6),
            "1M": calc_ret(-22),
            "YTD": ytd_ret
        }
    except: return None

def find_ticker(query):
    query = query.strip()
    for cat in ASSETS_CATEGORIZED.values():
        for sym, name in cat.items():
            if query in name: return sym
    return query.upper()

# --- 메인 기능 함수 ---
def run_full_report(chat_id):
    send_msg("📊 <b>전체 마켓 리포트를 생성 중입니다...</b>", chat_id)
    report = f"🌍 <b>글로벌 리포트 ({datetime.now().strftime('%H:%M')})</b>\n"
    report += "<code>(1D / 1W / 1M / YTD)</code>\n\n"
    
    for cat, stocks in ASSETS_CATEGORIZED.items():
        report += f"<b>[{cat}]</b>\n"
        for sym, name in stocks.items():
            d = get_rich_data(sym)
            if d:
                report += f"• {name}: {d['1D']:+.1f}/{d['1W']:+.1f}/{d['1M']:+.1f}/{d['YTD']:+.1f}%\n"
        report += "\n"
    send_msg(report, chat_id)

def run_portfolio_report(chat_id):
    global MY_PORTFOLIO
    MY_PORTFOLIO = load_pf() # 최신 데이터 로드
    if not MY_PORTFOLIO:
        send_msg("📝 등록된 포트폴리오가 없습니다.\n<code>/등록 삼성전자 72000 10</code>", chat_id)
        return

    send_msg("💰 <b>실시간 수익률 계산 중...</b>", chat_id)
    fx = get_rich_data("KRW=X")
    rate = fx['price'] if fx else 1350
    
    total_buy_krw = 0
    total_curr_krw = 0
    pf_detail = ""

    for sym, info in MY_PORTFOLIO.items():
        buy_p, amt = info
        d = get_rich_data(sym)
        if not d: continue
        
        is_usd = any(x in sym for x in ["-USD", "=F", ".HK", ".SZ", ".SS"]) or (not sym.endswith(".KS") and not sym.endswith(".KQ"))
        c_price = d['price']
        
        b_krw = (buy_p * amt * rate) if is_usd else (buy_p * amt)
        c_krw = (c_price * amt * rate) if is_usd else (c_price * amt)
        p_rate = ((c_price - buy_p) / buy_p) * 100
        
        total_buy_krw += b_krw
        total_curr_krw += c_krw
        emoji = "🔴" if p_rate > 0 else "🔵"
        pf_detail += f"{emoji} <b>{sym}</b>: {p_rate:+.2f}% (평단:{buy_p:,.0f})\n"

    total_profit = total_curr_krw - total_buy_krw
    total_rate = (total_profit / total_buy_krw * 100) if total_buy_krw != 0 else 0
    
    final_report = f"📋 <b>내 자산 현황</b>\n\n{pf_detail}"
    final_report += f"--------------------\n💰 <b>총 손익: {total_profit:+, .0f}원\n수익률: {total_rate:+.2f}%</b>"
    send_msg(final_report, chat_id)

def handle_commands():
    global last_update_id, MY_PORTFOLIO
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
                    parts = text.split()
                    if len(parts) == 4:
                        ticker = find_ticker(parts[1])
                        MY_PORTFOLIO[ticker] = [float(parts[2]), float(parts[3])]
                        save_pf(MY_PORTFOLIO) # 파일 저장
                        send_msg(f"✅ <b>{ticker}</b> 등록 완료!", cid)
                elif text.startswith('/s '):
                    ticker = find_ticker(text[3:])
                    d = get_rich_data(ticker)
                    if d:
                        send_msg(f"🔍 <b>{ticker}</b>\n가격: {d['price']:,.2f}\n1D:{d['1D']:+.1f}% 1W:{d['1W']:+.1f}% 1M:{d['1M']:+.1f}% YTD:{d['YTD']:+.1f}%", cid)
                elif text in ['포트', '포트폴리오', 'pf']:
                    run_portfolio_report(cid)
                elif text in ['리포트', '전체', 'all']:
                    run_full_report(cid)
                elif text in ['/start', '도움말']:
                    send_msg("🤖 <b>명령어</b>\n• 리포트 (전체 요약)\n• 포트 (내 수익률)\n• /등록 종목 평단 수량\n• /s 종목명 (상세조회)", cid)
    except: pass

if __name__ == "__main__":
    keep_alive()
    print("🚀 모든 기능이 통합된 최종 봇 실행 중...")
    while True:
        handle_commands()
        time.sleep(1)
