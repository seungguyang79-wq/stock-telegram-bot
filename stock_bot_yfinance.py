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
def home(): return "Global Full-Asset Bot is Online! ✅"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    Thread(target=run_server, daemon=True).start()

# --- 설정 및 데이터 ---
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"

MY_PORTFOLIO = {} # 텔레그램 /등록 명령어로 채워짐

# [기존 모든 자산군 완전 원복]
ASSETS_CATEGORIZED = {
    "🌐 지수 및 매크로": {
        "^KS11": "코스피", "^KQ11": "코스닥", "^GSPC": "S&P500", "^IXIC": "나스닥",
        "^HSI": "항셍지수", "HSTECH.HK": "항셍테크", "399006.SZ": "차이나넥스트", "000688.SS": "과창판 50",
        "KRW=X": "원/달러 환율", "^VIX": "공포지수(VIX)", "^TNX": "미 10년물 금리"
    },
    "🇺🇸 미국 M7": {
        "AAPL": "애플", "MSFT": "마이크로소프트", "GOOGL": "구글", "AMZN": "아마존", 
        "NVDA": "엔비디아", "META": "메타", "TSLA": "테슬라"
    },
    "🇰🇷 한국 주요주": {
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "005380.KS": "현대차", 
        "035420.KS": "NAVER", "035720.KS": "카카오"
    },
    "🇭🇰 홍콩/중국 M7+": {
        "0700.HK": "텐센트", "9988.HK": "알리바바", "3690.HK": "메이투안", 
        "1810.HK": "샤오미", "9888.HK": "바이두", "9999.HK": "넷이즈", "9618.HK": "JD닷컴"
    },
    "🪙 자산": { 
        "BTC-USD": "비트코인", "ETH-USD": "이더리움", "GC=F": "금", "SI=F": "은" 
    }
}

last_update_id = 0

# --- 공통 함수 ---
def send_msg(text, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=20)
    except: pass

def get_simple_data(symbol):
    try:
        t = yf.Ticker(symbol)
        h = t.history(period="5d")
        if h.empty: return None
        curr = h['Close'].iloc[-1]
        prev = h['Close'].iloc[-2]
        change = ((curr - prev) / prev) * 100
        return {"price": curr, "change": change}
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
    report = f"🌍 <b>글로벌 마켓 요약 ({datetime.now().strftime('%H:%M')})</b>\n\n"
    
    for cat, stocks in ASSETS_CATEGORIZED.items():
        report += f"<b>[{cat}]</b>\n"
        for sym, name in stocks.items():
            d = get_simple_data(sym)
            if d:
                report += f"• {name}: {d['change']:+.2f}%\n"
        report += "\n"
    
    send_msg(report, chat_id)

def run_portfolio_report(chat_id):
    if not MY_PORTFOLIO:
        send_msg("📝 등록된 포트폴리오가 없습니다.\n<code>/등록 삼성전자 137500 30</code> 형식으로 추가해 보세요!", chat_id)
        return

    send_msg("💰 <b>실시간 포트폴리오 수익률을 계산합니다...</b>", chat_id)
    fx = get_simple_data("KRW=X")
    rate = fx['price'] if fx else 1350
    
    total_buy_krw = 0
    total_curr_krw = 0
    pf_detail = ""

    for sym, info in MY_PORTFOLIO.items():
        buy_p, amt = info
        d = get_simple_data(sym)
        if not d: continue
        
        is_usd = any(x in sym for x in ["-USD", "=F", ".HK", ".SZ", ".SS"]) or (not sym.endswith(".KS") and not sym.endswith(".KQ"))
        c_price = d['price']
        
        # 해외 주식은 원화 환산 (간단 로직)
        b_krw = (buy_p * amt * rate) if is_usd else (buy_p * amt)
        c_krw = (c_price * amt * rate) if is_usd else (c_price * amt)
        p_rate = ((c_price - buy_p) / buy_p) * 100
        
        total_buy_krw += b_krw
        total_curr_krw += c_krw
        emoji = "📈" if p_rate > 0 else "📉"
        pf_detail += f"{emoji} <b>{sym}</b>\n   수익률: {p_rate:+.2f}% / 현재가: {c_price:,.2f}\n"

    total_profit = total_curr_krw - total_buy_krw
    total_rate = (total_profit / total_buy_krw * 100) if total_buy_krw != 0 else 0
    
    final_report = f"📋 <b>내 자산 현황 (원화 환산)</b>\n\n{pf_detail}"
    final_report += f"--------------------\n💰 <b>총 손익: {total_profit:+, .0f}원\n누적 수익률: {total_rate:+.2f}%</b>"
    
    send_msg(final_report, chat_id)

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
                    parts = text.split()
                    if len(parts) == 4:
                        ticker = find_ticker(parts[1])
                        MY_PORTFOLIO[ticker] = [float(parts[2]), float(parts[3])]
                        send_msg(f"✅ <b>{ticker}</b> 등록 완료!", cid)
                elif text.startswith('/s '):
                    ticker = find_ticker(text[3:])
                    d = get_simple_data(ticker)
                    if d: send_msg(f"🔍 <b>{ticker}</b>\n가격: {d['price']:,.2f}\n변동: {d['change']:+.2f}%", cid)
                elif text in ['포트', '포트폴리오', 'pf']:
                    run_portfolio_report(cid)
                elif text in ['리포트', '전체', 'all']:
                    run_full_report(cid)
                elif text in ['/help', '도움말', '/start']:
                    msg = ("🤖 <b>명령어 안내</b>\n"
                           "• <code>리포트</code>: 전체 시장 요약\n"
                           "• <code>포트</code>: 내 수익률 확인\n"
                           "• <code>/등록 종목 평단 수량</code>\n"
                           "• <code>/s 종목명</code>: 실시간 시세 검색")
                    send_msg(msg, cid)
    except: pass

if __name__ == "__main__":
    keep_alive()
    print("🚀 자산군 복구가 완료된 최종 봇 실행 중...")
    while True:
        handle_commands()
        time.sleep(1)
