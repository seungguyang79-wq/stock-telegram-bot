import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime
from flask import Flask
from threading import Thread
import gc

# --- Flask 서버 (Render 서버 유지용) ---
app = Flask(__name__)

@app.route('/')
def home(): 
    return "Stock Alert Bot is Running! ✅"

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

def run_server():
    # Render는 PORT 환경 변수를 통해 포트를 지정합니다.
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    """서버가 잠들지 않도록 별도 스레드에서 Flask 실행"""
    Thread(target=run_server, daemon=True).start()

# --- 설정 및 데이터 ---
# 발급받으신 토큰과 채팅 ID를 그대로 사용합니다.
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"

# 감시 및 리포트 대상 자산
ASSETS_CATEGORIZED = {
    "🌐 글로벌 주요 지수": {
        "^KS11": "코스피", "^KQ11": "코스닥", "^GSPC": "S&P500", "^IXIC": "나스닥",
        "^HSI": "항셍지수", "HSTECH.HK": "항셍테크", "399006.SZ": "차이나넥스트", "000688.SS": "과창판 50"
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

# 전역 변수
last_update_id = 0
alerted_stocks = set() # 당일 알림 발송 기록 (중복 방지)
ALERT_THRESHOLD = 5.0  # 변동성 알림 기준 (%)

# --- 데이터 수집 및 전송 함수 ---

def send_telegram_message(text, chat_id=TELEGRAM_CHAT_ID):
    """텔레그램 메시지 전송"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        res = requests.post(url, json=payload, timeout=20)
        res.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ 메시지 전송 실패: {e}")
        return False

def get_market_data(symbol):
    """수익률 데이터 수집 (메모리 최적화 버전)"""
    try:
        ticker = yf.Ticker(symbol)
        # 5일치 데이터만 가져와서 속도와 메모리 확보
        hist = ticker.history(period="5d")
        if len(hist) < 2: return None
        
        curr = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2]
        change = ((curr - prev) / prev) * 100
        
        return {"change": change, "price": curr}
    except Exception as e:
        print(f"❌ {symbol} 데이터 오류: {e}")
        return None

def check_volatility_and_report(is_scheduled=False):
    """시장을 감시하고 변동성 알림 또는 정기 리포트 전송"""
    global alerted_stocks
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"🔍 시장 체크 중... ({now_str})")
    
    today_key = datetime.now().strftime("%Y%m%d")
    report_msg = f"🌍 <b>글로벌 마켓 정기 리포트</b>\n📅 {now_str}\n\n"
    
    for cat, stocks in ASSETS_CATEGORIZED.items():
        if is_scheduled: report_msg += f"<b>[{cat}]</b>\n"
        
        for sym, name in stocks.items():
            data = get_market_data(sym)
            if not data: continue
            
            # 1. 변동성 알림 체크 (기준 초과 시 즉시 발송)
            alert_id = f"{today_key}_{sym}"
            if abs(data['change']) >= ALERT_THRESHOLD and alert_id not in alerted_stocks:
                emoji = "📈" if data['change'] > 0 else "📉"
                alert_text = (
                    f"{emoji} <b>[변동성 알림] {name}</b>\n"
                    f"변동률: {data['change']:+.2f}%\n"
                    f"현재가: {data['price']:,.2f}"
                )
                if send_telegram_message(alert_text):
                    alerted_stocks.add(alert_id)
            
            # 2. 정기 리포트용 메시지 빌드
            if is_scheduled:
                report_msg += f"• {name}: {data['change']:+.2f}%\n"
        
        if is_scheduled: report_msg += "\n"

    # 정기 리포트 시간일 경우 전체 메시지 전송
    if is_scheduled:
        send_telegram_message(report_msg)
    
    # 메모리 정리
    gc.collect()

def reset_daily_data():
    """매일 자정 알림 기록 초기화"""
    global alerted_stocks
    alerted_stocks.clear()
    print("♻️ 일일 데이터 초기화 완료")

def handle_commands():
    """사용자 명령어 확인 및 응답"""
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": last_update_id + 1, "timeout": 5}, timeout=10)
        updates = r.json().get('result', [])
        for u in updates:
            last_update_id = u['update_id']
            if 'message' in u and 'text' in u['message']:
                text = u['message']['text'].lower()
                cid = u['message']['chat']['id']
                
                if text in ['/start', '도움말', 'help']:
                    send_telegram_message("🤖 <b>주식 알림 봇</b>\n\n- 10분마다 5% 급등락 감시\n- 정기 리포트 자동 발송", cid)
                elif text in ['리포트', 'all', '전체']:
                    check_volatility_and_report(is_scheduled=True)
    except:
        pass

# --- 메인 루프 ---

if __name__ == "__main__":
    print("🚀 봇 가동 시작...")
    keep_alive()
    
    # 1. 스케줄 설정
    # 10분마다 급변동 체크
    schedule.every(10).minutes.do(check_volatility_and_report, is_scheduled=False)
    # 정기 리포트 시간 설정
    report_times = ["09:05", "10:35", "15:40", "17:05", "22:35", "06:05"]
    for t in report_times:
        schedule.every().day.at(t).do(check_volatility_and_report, is_scheduled=True)
    # 자정 초기화
    schedule.every().day.at("00:00").do(reset_daily_data)
    
    send_telegram_message("🤖 봇 가동 시작!\n실시간 모니터링 및 정기 리포트를 시작합니다.")

    try:
        while True:
            schedule.run_pending()
            handle_commands()
            time.sleep(1)
    except KeyboardInterrupt:
        print("👋 종료")
