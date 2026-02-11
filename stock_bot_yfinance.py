import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime
from flask import Flask
from threading import Thread
import io
import gc

# matplotlib 설정 (서버 환경용)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Flask 서버 (Render 서비스 유지용)
app = Flask(__name__)

@app.route('/')
def home(): return "Stock Bot is Running! ✅"

@app.route('/health')
def health(): return "OK", 200

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    Thread(target=run_server, daemon=True).start()

# --- 설정 및 데이터 ---
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"
last_update_id = 0
my_portfolio = {} # 포트폴리오 데이터 (메모리 저장)

# 종목 설정 (M7 + 한국 주요 종목 + 자산)
ASSETS = {
    # --- 미국 주식 (M7) ---
    "AAPL": ["애플", "Apple"],
    "MSFT": ["마이크로소프트", "MSFT"],
    "GOOGL": ["구글", "Alphabet"],
    "AMZN": ["아마존", "Amazon"],
    "NVDA": ["엔비디아", "Nvidia"],
    "META": ["메타", "Meta"],
    "TSLA": ["테슬라", "Tesla"],
    
    # --- 한국 주식 ---
    "005930.KS": ["삼성전자", "Samsung"],
    "000660.KS": ["SK하이닉스", "Hynix"],
    "005380.KS": ["현대차", "Hyundai"],
    "035420.KS": ["NAVER", "Naver"],
    "035720.KS": ["카카오", "Kakao"],
    
    # --- 자산 (코인, 귀금속) ---
    "BTC-USD": ["비트코인", "Bitcoin"],
    "ETH-USD": ["이더리움", "Ethereum"],
    "GC=F": ["금", "Gold"],
    "SI=F": ["은", "Silver"]
}

# --- 보조 기능 함수 ---
def get_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

def get_news(symbol):
    try:
        news = yf.Ticker(symbol).news[:2]
        return "".join([f" • <a href='{n['link']}'>{n['title'][:25]}...</a>\n" for n in news])
    except: return "  (뉴스 없음)\n"

def send_message(text, chat_id=None):
    if not chat_id: chat_id = TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
    except: pass

def send_photo(image_buffer, caption="", chat_id=None):
    if not chat_id: chat_id = TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try: requests.post(url, files={'photo': ('chart.png', image_buffer)}, data={'chat_id': chat_id, 'caption': caption}, timeout=30)
    except: pass

# --- 핵심 로직 함수 ---
def get_asset_info(symbol, name):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo")
        if hist.empty: return None
        
        curr = hist['Close'].iloc[-1]
        change = ((curr - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100)
        rsi = get_rsi(hist['Close']).iloc[-1]
        news = get_news(symbol)
        
        unit = "원" if ".KS" in symbol else "$"
        detail = (f"📊 <b>{name}</b> ({symbol})\n"
                  f"💰 현재가: {curr:,.2f}{unit} ({change:+.2f}%)\n"
                  f"📈 RSI: {rsi:.1f} ({'🔥과열' if rsi>70 else '❄️침체' if rsi<30 else '보통'})\n"
                  f"📰 <b>최신 뉴스</b>\n{news}")
        return {'text': f"🔹 {name}: {curr:,.0f}{unit} ({change:+.1f}%)", 'detail': detail}
    except: return None

def create_yield_chart():
    try:
        returns = {}
        for sym, names in ASSETS.items():
            h = yf.Ticker(sym).history(period="1mo")
            if len(h) > 2:
                returns[names[1]] = ((h['Close'].iloc[-1] - h['Close'].iloc[0]) / h['Close'].iloc[0]) * 100
        
        fig, ax = plt.subplots(figsize=(10, 8))
        colors = ['#2ecc71' if v > 0 else '#e74c3c' for v in returns.values()]
        ax.barh(list(returns.keys()), list(returns.values()), color=colors)
        ax.set_title("30-Day Returns (%)", fontsize=15)
        ax.axvline(0, color='black', linewidth=0.8)
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        plt.close('all')
        gc.collect()
        return buf
    except: return None

def calculate_portfolio():
    if not my_portfolio: return "📝 등록된 포트폴리오가 없습니다.\n'포트폴리오 추가 [이름] [단가] [수량]'"
    total_buy, total_eval, report = 0, 0, "💰 <b>내 포트폴리오</b>\n\n"
    for name, data in my_portfolio.items():
        try:
            curr = yf.Ticker(data['symbol']).history(period="1d")['Close'].iloc[-1]
            buy_total, eval_total = data['price'] * data['count'], curr * data['count']
            total_buy += buy_total; total_eval += eval_total
            ratio = (eval_total - buy_total) / buy_total * 100
            unit = "원" if ".KS" in data['symbol'] else "$"
            report += f"📍 <b>{name}</b>\n   수익률: {ratio:+.2f}% | 수익: {eval_total-buy_total:,.0f}{unit}\n"
        except: continue
    
    if total_buy > 0:
        total_profit = total_eval - total_buy
        report += f"\n{'='*20}\n💵 총 수익: {total_profit:,.0f} ({total_profit/total_buy*100-100:+.2f}%)"
    return report

def handle_command(text, chat_id):
    global my_portfolio
    text = text.lower().strip()
    
    if text in ['전체', '리포트', 'all']:
        send_message("🌍 전체 리포트 생성 중...")
        msg = f"🌍 <b>금융 리포트</b> ({datetime.now().strftime('%m/%d %H:%M')})\n"
        for sym, names in ASSETS.items():
            info = get_asset_info(sym, names[0])
            if info: msg += info['text'] + "\n"
        send_message(msg, chat_id)
    
    elif text in ['차트', 'chart']:
        send_message("📊 수익률 차트 분석 중...")
        chart = create_yield_chart()
        if chart: send_photo(chart, "📊 최근 30일 수익률 비교", chat_id)
        
    elif text.startswith("포트폴리오 추가"):
        try:
            p = text.split()
            name_in, price, count = p[2], float(p[3]), float(p[4])
            for sym, names in ASSETS.items():
                if name_in in names[0].lower() or name_in in names[1].lower():
                    my_portfolio[names[0]] = {"symbol": sym, "price": price, "count": count}
                    send_message(f"✅ {names[0]} 등록 완료!", chat_id)
                    return
            send_message("❌ 종목을 찾을 수 없습니다.", chat_id)
        except: send_message("❌ 사용법: 포트폴리오 추가 삼성 70000 10", chat_id)
        
    elif text in ['포트폴리오', 'pf']:
        send_message(calculate_portfolio(), chat_id)

    else:
        for sym, names in ASSETS.items():
            if text in names[0].lower() or text in names[1].lower():
                info = get_asset_info(sym, names[0])
                if info: send_message(info['detail'], chat_id)
                return

def check_messages():
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": last_update_id + 1, "timeout": 10}, timeout=15).json()
        for u in r.get('result', []):
            last_update_id = u['update_id']
            if 'message' in u and 'text' in u['message']:
                handle_command(u['message']['text'], u['message']['chat']['id'])
    except: pass

def scheduled_job():
    report = calculate_portfolio()
    send_message("⏰ <b>정기 자산 보고</b>\n" + report)

if __name__ == "__main__":
    keep_alive()
    # 보고 시간 설정
    times = ["09:00", "15:40", "22:30"]
    for t in times: schedule.every().day.at(t).do(scheduled_job)
    
    send_message("🚀 <b>알림 봇 가동!</b>\n\n• 전체: 시장 리포트\n• 차트: 30일 수익률\n• pf: 수익률 계산\n• 종목명: 상세 정보")
    
    try:
        while True:
            schedule.run_pending()
            check_messages()
            time.sleep(5)
    except KeyboardInterrupt:
        print("Bot Stopped")
