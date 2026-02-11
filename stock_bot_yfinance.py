import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime
import pandas as pd
from flask import Flask
from threading import Thread
import io
import gc

# matplotlib 설정 (서버 환경용)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Flask 서버 (Render 서비스 유지용)
app = Flask(__name__)

@app.route('/')
def home(): return "Global Stock Bot is Running! ✅"

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
my_portfolio = {} 

# 국가 및 자산군별 종목 분류
ASSETS_CATEGORIZED = {
    "🌐 글로벌 주요 지수": {
        "^KS11": "코스피", "^KQ11": "코스닥", 
        "^GSPC": "S&P500", "^IXIC": "나스닥",
        "^HSI": "항셍지수", "HSTECH.HK": "항셍테크",
        "399006.SZ": "차이나넥스트", "000688.SS": "과창판 50"
    },
    "🇺🇸 미국 M7": {
        "AAPL": "애플", "MSFT": "마이크로소프트", "GOOGL": "구글",
        "AMZN": "아마존", "NVDA": "엔비디아", "META": "메타", "TSLA": "테슬라"
    },
    "🇰🇷 한국 주요주": {
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", 
        "005380.KS": "현대차", "035420.KS": "NAVER", "035720.KS": "카카오"
    },
    "🇭🇰 홍콩/중국 M7+": {
        "0700.HK": "텐센트", "9988.HK": "알리바바", "3690.HK": "메이투안",
        "1810.HK": "샤오미", "9888.HK": "바이두", "9999.HK": "넷이즈", "9618.HK": "JD닷컴"
    },
    "🪙 자산 (코인/금속)": {
        "BTC-USD": "비트코인", "ETH-USD": "이더리움", 
        "GC=F": "금", "SI=F": "은"
    }
}

ALL_ASSETS = {sym: name for cat in ASSETS_CATEGORIZED.values() for sym, name in cat.items()}

# --- 기능 함수 ---
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

def get_all_returns(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2y")
        if len(hist) < 2: return None
        curr = hist['Close'].iloc[-1]
        p_1d, p_1w, p_1m = hist['Close'].iloc[-2], hist['Close'].iloc[-6], hist['Close'].iloc[-22]
        start_of_year = datetime(datetime.now().year, 1, 1).date()
        ytd_data = hist.loc[hist.index.date >= start_of_year]
        p_ytd = ytd_data['Close'].iloc[0] if not ytd_data.empty else hist['Close'].iloc[0]
        def c(p): return ((curr - p) / p * 100)
        return {"1D": c(p_1d), "1W": c(p_1w), "1M": c(p_1m), "YTD": c(p_ytd), "curr": curr}
    except: return None

def create_multi_period_chart():
    try:
        chart_data = []
        for cat_name, stocks in ASSETS_CATEGORIZED.items():
            for sym, name in stocks.items():
                r = get_all_returns(sym)
                if r: chart_data.append({'Name': f"{name}({cat_name[:2]})", '7D': r['1W'], '30D': r['1M'], 'YTD': r['YTD']})
        
        df = pd.DataFrame(chart_data)
        fig, ax = plt.subplots(figsize=(12, 18))
        y = np.arange(len(df))
        ax.barh(y + 0.25, df['7D'], 0.25, label='7 Days', color='#3498db')
        ax.barh(y, df['30D'], 0.25, label='30 Days', color='#2ecc71')
        ax.barh(y - 0.25, df['YTD'], 0.25, label='YTD', color='#f1c40f')
        ax.set_yticks(y); ax.set_yticklabels(df['Name'])
        ax.legend(); ax.axvline(0, color='black', linewidth=0.8); ax.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        buf = io.BytesIO(); plt.savefig(buf, format='png', dpi=120); buf.seek(0)
        plt.close('all'); gc.collect()
        return buf
    except: return None

def handle_command(text, chat_id):
    text = text.lower().strip()
    if text in ['전체', '리포트', 'all']:
        msg = f"🌍 <b>글로벌 마켓 통합 리포트</b>\n({datetime.now().strftime('%m/%d %H:%M')})\n"
        msg += "<code>단위: 1D / 1W / YTD</code>\n"
        
        for cat, stocks in ASSETS_CATEGORIZED.items():
            msg += f"\n<b>[{cat}]</b>\n"
            for sym, name in stocks.items():
                r = get_all_returns(sym)
                if r:
                    # 일간, 주간, 연초대비 수익률을 한 줄에 표시
                    msg += f" • {name}: {r['1D']:+.1f}% / {r['1W']:+.1f}% / {r['YTD']:+.1f}%\n"
        send_message(msg, chat_id)
    
    elif text in ['차트', 'chart']:
        send_message("📊 통합 수익률 차트 생성 중...", chat_id)
        chart = create_multi_period_chart()
        if chart: send_photo(chart, "📊 기간별 수익률 분석 (Blue: 7D / Green: 30D / Yellow: YTD)", chat_id)

    elif text in ['포트폴리오', 'pf']:
        if not my_portfolio:
            send_message("📝 등록된 포트폴리오가 없습니다. '포트폴리오 추가 [이름] [단가] [수량]'으로 등록하세요.", chat_id)
        else:
            msg = "💰 <b>내 자산 멀티 수익률</b>\n<code>단위: 현재가 / 수익률 / YTD</code>\n"
            for cat, stocks in ASSETS_CATEGORIZED.items():
                cat_msg = ""
                for sym, name in stocks.items():
                    if name in my_portfolio:
                        d = my_portfolio[name]
                        r = get_all_returns(sym)
                        if r:
                            gain = (r['curr'] - d['price']) / d['price'] * 100
                            unit = "HKD" if ".HK" in sym or ".SS" in sym else "원" if ".KS" in sym else "$"
                            cat_msg += f" • {name}: {r['curr']:,.0f}{unit} / {gain:+.1f}% / {r['YTD']:+.1f}%\n"
                if cat_msg: msg += f"\n<b>[{cat}]</b>\n" + cat_msg
            send_message(msg, chat_id)

    else:
        for sym, name in ALL_ASSETS.items():
            if text in name.lower() or text in sym.lower():
                r = get_all_returns(sym)
                if r:
                    unit = "HKD" if ".HK" in sym or ".SS" in sym or ".SZ" in sym else "원" if ".KS" in sym else "$"
                    msg = f"📊 <b>{name}</b> ({sym})\n💰 현재가: {r['curr']:,.2f}{unit}\n\n1D: {r['1D']:+.2f}%\n1W: {r['1W']:+.2f}%\n1M: {r['1M']:+.2f}%\nYTD: {r['YTD']:+.2f}%\n\n📰 <b>최신 뉴스</b>\n{get_news(sym)}"
                    send_message(msg, chat_id)
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

# --- 메인 실행부 ---
if __name__ == "__main__":
    keep_alive()
    
    # 6단계 자동 스케줄 보고
    schedule.every().day.at("09:05").do(lambda: handle_command('전체', TELEGRAM_CHAT_ID)) # 국장 개장
    schedule.every().day.at("10:35").do(lambda: handle_command('전체', TELEGRAM_CHAT_ID)) # 항셍 개장
    schedule.every().day.at("15:40").do(lambda: handle_command('전체', TELEGRAM_CHAT_ID)) # 국장 마감
    schedule.every().day.at("17:05").do(lambda: handle_command('전체', TELEGRAM_CHAT_ID)) # 항셍 마감
    schedule.every().day.at("22:35").do(lambda: handle_command('전체', TELEGRAM_CHAT_ID)) # 미장 개장
    schedule.every().day.at("06:05").do(lambda: handle_command('전체', TELEGRAM_CHAT_ID)) # 미장 마감

    print("🚀 글로벌 멀티 리포트 봇 가동!")
    send_message("✅ <b>글로벌 멀티 리포트 봇 가동</b>\n이제 '전체' 리포트에서 1D/1W/YTD 수익률을 한 번에 확인하세요.")

    while True:
        schedule.run_pending()
        check_messages()
        time.sleep(5)
