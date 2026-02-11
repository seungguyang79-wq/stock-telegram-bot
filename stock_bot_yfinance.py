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

# --- matplotlib 및 한글 폰트 설정 ---
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# 나눔고딕 폰트 다운로드 및 설정 (Render/Linux 환경 대응)
def setup_font():
    font_url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
    res = requests.get(font_url)
    with open("NanumGothic.ttf", "wb") as f:
        f.write(res.content)
    fe = fm.FontEntry(fname="NanumGothic.ttf", name="NanumGothic")
    fm.font_manager.ttflist.insert(0, fe)
    plt.rcParams.update({'font.family': "NanumGothic", 'axes.unicode_minus': False})

setup_font() # 폰트 설정 실행

# --- Flask 서버 ---
app = Flask(__name__)
@app.route('/')
def home(): return "Global Stock Bot is Running! ✅"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run_server, daemon=True).start()

# --- 설정 및 데이터 ---
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"

ASSETS_CATEGORIZED = {
    "🌐 글로벌 주요 지수": {
        "^KS11": "코스피", "^KQ11": "코스닥", "^GSPC": "S&P500", "^IXIC": "나스닥",
        "^HSI": "항셍지수", "HSTECH.HK": "항셍테크", "399006.SZ": "차이나넥스트", "000688.SS": "과창판 50"
    },
    "🇺🇸 미국 M7": {
        "AAPL": "애플", "MSFT": "마이크로소프트", "GOOGL": "구글", "AMZN": "아마존", "NVDA": "엔비디아", "META": "메타", "TSLA": "테슬라"
    },
    "🇰🇷 한국 주요주": {
        "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "005380.KS": "현대차", "035420.KS": "NAVER", "035720.KS": "카카오"
    },
    "🇭🇰 홍콩/중국 M7+": {
        "0700.HK": "텐센트", "9988.HK": "알리바바", "3690.HK": "메이투안", "1810.HK": "샤오미", "9888.HK": "바이두", "9999.HK": "넷이즈", "9618.HK": "JD닷컴"
    },
    "🪙 자산": { "BTC-USD": "비트코인", "ETH-USD": "이더리움", "GC=F": "금", "SI=F": "은" }
}

ALL_ASSETS = {sym: name for cat in ASSETS_CATEGORIZED.values() for sym, name in cat.items()}

# --- 핵심 기능 함수 ---
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
                if r:
                    # 국가 이모지 대신 텍스트로 표기 (폰트 안정성)
                    label = f"{name}" 
                    chart_data.append({'Name': label, '7D': r['1W'], '30D': r['1M'], 'YTD': r['YTD']})
        
        df = pd.DataFrame(chart_data)
        fig, ax = plt.subplots(figsize=(10, 16)) # 세로로 더 길게 조정
        y = np.arange(len(df))
        
        ax.barh(y + 0.25, df['7D'], 0.25, label='7일', color='#3498db')
        ax.barh(y, df['30D'], 0.25, label='30일', color='#2ecc71')
        ax.barh(y - 0.25, df['YTD'], 0.25, label='YTD', color='#f1c40f')
        
        ax.set_yticks(y)
        ax.set_yticklabels(df['Name'], fontsize=10)
        ax.set_title(f"글로벌 마켓 수익률 현황 ({datetime.now().strftime('%Y-%m-%d')})", fontsize=15)
        ax.legend()
        ax.axvline(0, color='black', linewidth=1)
        ax.grid(axis='x', linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        buf.seek(0)
        plt.close('all')
        gc.collect()
        return buf
    except Exception as e:
        print(f"Chart Error: {e}")
        return None

def handle_command(text, chat_id):
    text = text.lower().strip()
    if text in ['전체', '리포트', 'all']:
        msg = f"🌍 <b>글로벌 마켓 통합 리포트</b>\n(단위: 1D / 1W / YTD)\n"
        for cat, stocks in ASSETS_CATEGORIZED.items():
            msg += f"\n<b>[{cat}]</b>\n"
            for sym, name in stocks.items():
                r = get_all_returns(sym)
                if r: msg += f" • {name}: {r['1D']:+.1f}% / {r['1W']:+.1f}% / {r['YTD']:+.1f}%\n"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
    
    elif text in ['차트', 'chart']:
        chart = create_multi_period_chart()
        if chart:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto", files={'photo': ('chart.png', chart)}, data={'chat_id': chat_id, 'caption': "📊 기간별 수익률 분석 (파랑:7일 / 초록:30일 / 노랑:YTD)"})

def check_messages():
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": last_update_id + 1, "timeout": 10}).json()
        for u in r.get('result', []):
            last_update_id = u['update_id']
            if 'message' in u and 'text' in u['message']:
                handle_command(u['message']['text'], u['message']['chat']['id'])
    except: pass

if __name__ == "__main__":
    keep_alive()
    # 6단계 스케줄링 로직 (축약)
    schedule.every().day.at("09:05").do(lambda: handle_command('전체', TELEGRAM_CHAT_ID))
    schedule.every().day.at("10:35").do(lambda: handle_command('전체', TELEGRAM_CHAT_ID))
    schedule.every().day.at("15:40").do(lambda: handle_command('전체', TELEGRAM_CHAT_ID))
    schedule.every().day.at("17:05").do(lambda: handle_command('전체', TELEGRAM_CHAT_ID))
    schedule.every().day.at("22:35").do(lambda: handle_command('전체', TELEGRAM_CHAT_ID))
    schedule.every().day.at("06:05").do(lambda: handle_command('전체', TELEGRAM_CHAT_ID))

    while True:
        schedule.run_pending()
        check_messages()
        time.sleep(5)
