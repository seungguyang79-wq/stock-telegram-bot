import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime
import pandas as pd
from flask import Flask
from threading import Thread
import gc

# --- Flask 서버 (Render 유지용) ---
app = Flask(__name__)

@app.route('/')
def home(): 
    return "Multi-Period Stock Bot is Running! ✅"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    Thread(target=run_server, daemon=True).start()

# --- 설정 및 데이터 ---
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"

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
alerted_stocks = set()
ALERT_THRESHOLD = 5.0 

# --- 수익률 계산 핵심 함수 ---

def get_multi_period_returns(symbol):
    """1D, 1W, 1M, YTD 수익률을 계산합니다."""
    try:
        ticker = yf.Ticker(symbol)
        # YTD 계산을 위해 최대 2년치 데이터를 가져옵니다.
        hist = ticker.history(period="2y")
        if len(hist) < 2: return None
        
        curr = hist['Close'].iloc[-1]
        
        # 각 기간별 이전 가격 추출 (안전하게 인덱스 확인)
        p_1d = hist['Close'].iloc[-2]
        p_1w = hist['Close'].iloc[-6] if len(hist) >= 6 else hist['Close'].iloc[0]
        p_1m = hist['Close'].iloc[-22] if len(hist) >= 22 else hist['Close'].iloc[0]
        
        # YTD (연초 대비) 가격 추출
        start_of_year = datetime(datetime.now().year, 1, 1).date()
        ytd_data = hist.loc[hist.index.date >= start_of_year]
        p_ytd = ytd_data['Close'].iloc[0] if not ytd_data.empty else hist['Close'].iloc[0]
        
        def calc_ret(p_old):
            return ((curr - p_old) / p_old * 100)

        return {
            "price": curr,
            "1D": calc_ret(p_1d),
            "1W": calc_ret(p_1w),
            "1M": calc_ret(p_1m),
            "YTD": calc_ret(p_ytd)
        }
    except Exception as e:
        print(f"❌ {symbol} 데이터 오류: {e}")
        return None

def send_telegram_message(text, chat_id=TELEGRAM_CHAT_ID):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=20)
        return True
    except: return False

def market_opening_alert(market_name):
    send_telegram_message(f"🔔 <b>{market_name} 시장 개장 10분 전!</b>\n오늘도 성공적인 투자 되세요! 📈")

def check_market_logic(is_report=False):
    global alerted_stocks
    now = datetime.now()
    today_key = now.strftime("%Y%m%d")
    
    if is_report:
        report_msg = f"🌍 <b>글로벌 마켓 통합 리포트</b>\n📅 {now.strftime('%Y-%m-%d %H:%M')}\n"
        report_msg += "<code>(1D / 1W / 1M / YTD)</code>\n\n"
    
    for cat, stocks in ASSETS_CATEGORIZED.items():
        if is_report: report_msg += f"<b>[{cat}]</b>\n"
        
        for sym, name in stocks.items():
            data = get_multi_period_returns(sym)
            if not data: continue
            
            # 1. 변동성 알림 (1D 기준)
            alert_id = f"{today_key}_{sym}"
            if abs(data['1D']) >= ALERT_THRESHOLD and alert_id not in alerted_stocks:
                emoji = "📈" if data['1D'] > 0 else "📉"
                alert_text = (f"{emoji} <b>변동성 경보: {name}</b>\n"
                              f"변동률: {data['1D']:+.2f}%\n"
                              f"현재가: {data['price']:,.2f}")
                if send_telegram_message(alert_text):
                    alerted_stocks.add(alert_id)
            
            # 2. 정기 리포트 메시지 빌드
            if is_report:
                report_msg += f"• {name}: {data['1D']:+.1f}% / {data['1W']:+.1f}% / {data['1M']:+.1f}% / {data['YTD']:+.1f}%\n"
        
        if is_report: report_msg += "\n"
    
    if is_report: send_telegram_message(report_msg)
    gc.collect()

def search_stock(query, chat_id):
    symbol = None
    for cat in ASSETS_CATEGORIZED.values():
        for s, name in cat.items():
            if query in name: symbol = s; break
    if not symbol: symbol = query.upper()
    
    data = get_multi_period_returns(symbol)
    if data:
        msg = (f"🔍 <b>검색 결과: {symbol}</b>\n"
               f"현재가: {data['price']:,.2f}\n"
               f"--------------------\n"
               f"1D (어제): {data['1D']:+.2f}%\n"
               f"1W (1주): {data['1W']:+.2f}%\n"
               f"1M (1달): {data['1M']:+.2f}%\n"
               f"YTD (연초): {data['YTD']:+.2f}%")
        send_telegram_message(msg, chat_id)
    else:
        send_telegram_message(f"❌ '{query}' 정보를 찾을 수 없습니다.", chat_id)

def handle_commands():
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": last_update_id + 1, "timeout": 5}, timeout=10)
        for u in r.json().get('result', []):
            last_update_id = u['update_id']
            if 'message' in u and 'text' in u['message']:
                text = u['message']['text']
                cid = u['message']['chat']['id']
                if text.startswith('/s '): search_stock(text[3:].strip(), cid)
                elif text in ['리포트', '전체', 'all']: check_market_logic(is_report=True)
    except: pass

if __name__ == "__main__":
    keep_alive()
    schedule.every(10).minutes.do(check_market_logic, is_report=False)
    report_times = ["09:05", "10:35", "15:40", "17:05", "22:35", "06:05"]
    for t in report_times:
        schedule.every().day.at(t).do(check_market_logic, is_report=True)
    schedule.every().day.at("08:50").do(market_opening_alert, "국내(KOSPI)")
    schedule.every().day.at("22:20").do(market_opening_alert, "미국(나스닥)")
    schedule.every().day.at("00:00").do(lambda: alerted_stocks.clear())

    print("🚀 4개 기간 수익률 봇 가동!")
    while True:
        schedule.run_pending()
        handle_commands()
        time.sleep(1)
