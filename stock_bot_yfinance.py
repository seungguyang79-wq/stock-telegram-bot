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

def setup_font():
    """Render 서버 환경에서 한글 깨짐 방지를 위해 폰트를 다운로드하고 등록합니다."""
    font_url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
    font_path = "NanumGothic.ttf"
    try:
        # 폰트가 없을 경우에만 다운로드
        if not os.path.exists(font_path):
            print("📥 한글 폰트 다운로드 중...")
            res = requests.get(font_url, timeout=30)
            res.raise_for_status()
            with open(font_path, "wb") as f:
                f.write(res.content)
            print("✅ 폰트 다운로드 완료")
        
        # 폰트 등록
        fe = fm.FontEntry(fname=font_path, name="NanumGothic")
        fm.fontManager.ttflist.insert(0, fe)
        
        # 기본 폰트 설정 및 마이너스 기호 깨짐 방지
        plt.rcParams.update({
            'font.family': "NanumGothic",
            'axes.unicode_minus': False,
            'font.size': 10
        })
        print("✅ 한글 폰트(나눔고딕) 설정 완료")
    except Exception as e:
        print(f"❌ 폰트 설정 중 오류 발생: {e}")
        # 폰트 설정 실패 시 기본 설정
        plt.rcParams['axes.unicode_minus'] = False

setup_font()

# --- Flask 서버 (Render 유지용) ---
app = Flask(__name__)

@app.route('/')
def home(): 
    return "Global Stock Bot is Running! ✅"

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

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

ALL_ASSETS = {sym: name for cat in ASSETS_CATEGORIZED.values() for sym, name in cat.items()}

# 전역 변수
last_update_id = 0

# --- 데이터 수집 및 차트 생성 ---
def get_all_returns(symbol):
    """주어진 심볼에 대한 수익률 계산"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2y")
        
        if len(hist) < 2: 
            return None
        
        curr = hist['Close'].iloc[-1]
        
        # 안전한 인덱스 접근
        p_1d = hist['Close'].iloc[-2] if len(hist) >= 2 else curr
        p_1w = hist['Close'].iloc[-6] if len(hist) >= 6 else curr
        p_1m = hist['Close'].iloc[-22] if len(hist) >= 22 else curr
        
        # YTD 계산
        start_of_year = datetime(datetime.now().year, 1, 1).date()
        ytd_data = hist.loc[hist.index.date >= start_of_year]
        p_ytd = ytd_data['Close'].iloc[0] if not ytd_data.empty else hist['Close'].iloc[0]
        
        def calc_return(prev_price): 
            if prev_price == 0:
                return 0
            return ((curr - prev_price) / prev_price * 100)
        
        return {
            "1D": calc_return(p_1d), 
            "1W": calc_return(p_1w), 
            "1M": calc_return(p_1m), 
            "YTD": calc_return(p_ytd), 
            "curr": curr
        }
    except Exception as e:
        print(f"❌ {symbol} 데이터 수집 실패: {e}")
        return None

def create_multi_period_chart():
    """다중 기간 수익률 차트 생성"""
    try:
        chart_data = []
        for cat_name, stocks in ASSETS_CATEGORIZED.items():
            for sym, name in stocks.items():
                r = get_all_returns(sym)
                if r:
                    chart_data.append({
                        'Name': name, 
                        '7D': r['1W'], 
                        '30D': r['1M'], 
                        'YTD': r['YTD']
                    })
        
        if not chart_data:
            print("❌ 차트 데이터가 없습니다.")
            return None
        
        df = pd.DataFrame(chart_data)
        fig, ax = plt.subplots(figsize=(10, 18))
        y = np.arange(len(df))
        
        # 막대 그래프
        ax.barh(y + 0.25, df['7D'], 0.25, label='7일', color='#3498db')
        ax.barh(y, df['30D'], 0.25, label='30일', color='#2ecc71')
        ax.barh(y - 0.25, df['YTD'], 0.25, label='YTD', color='#f1c40f')
        
        ax.set_yticks(y)
        ax.set_yticklabels(df['Name'])
        ax.set_xlabel('수익률 (%)')
        ax.set_title(f"글로벌 수익률 현황 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
        ax.legend()
        ax.axvline(0, color='black', linewidth=1)
        ax.grid(axis='x', linestyle='--', alpha=0.4)
        
        plt.tight_layout()
        
        # 이미지 버퍼에 저장
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close('all')
        gc.collect()
        
        return buf
    except Exception as e:
        print(f"❌ 차트 생성 실패: {e}")
        plt.close('all')
        gc.collect()
        return None

def send_telegram_message(text, chat_id=TELEGRAM_CHAT_ID):
    """텔레그램 메시지 전송"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        response = requests.post(url, 
                                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                                timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ 메시지 전송 실패: {e}")
        return False

def send_telegram_photo(photo_buffer, caption, chat_id=TELEGRAM_CHAT_ID):
    """텔레그램 사진 전송"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        response = requests.post(url,
                                files={'photo': ('chart.png', photo_buffer, 'image/png')},
                                data={'chat_id': chat_id, 'caption': caption},
                                timeout=60)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ 사진 전송 실패: {e}")
        return False

def handle_command(text, chat_id):
    """명령어 처리"""
    text = text.lower().strip()
    
    if text in ['전체', '리포트', 'all', '/start']:
        print(f"📊 전체 리포트 생성 중... (요청자: {chat_id})")
        msg = f"🌍 <b>글로벌 마켓 통합 리포트</b>\n"
        msg += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        msg += f"(단위: 1D / 1W / YTD)\n"
        
        for cat, stocks in ASSETS_CATEGORIZED.items():
            msg += f"\n<b>[{cat}]</b>\n"
            for sym, name in stocks.items():
                r = get_all_returns(sym)
                if r: 
                    msg += f" • {name}: {r['1D']:+.1f}% / {r['1W']:+.1f}% / {r['YTD']:+.1f}%\n"
                else:
                    msg += f" • {name}: 데이터 없음\n"
        
        send_telegram_message(msg, chat_id)
    
    elif text in ['차트', 'chart']:
        print(f"📈 차트 생성 중... (요청자: {chat_id})")
        chart = create_multi_period_chart()
        if chart:
            caption = "📊 기간별 수익률 분석\n🔵 7일 | 🟢 30일 | 🟡 YTD"
            send_telegram_photo(chart, caption, chat_id)
        else:
            send_telegram_message("❌ 차트 생성에 실패했습니다.", chat_id)
    
    elif text in ['도움말', 'help', '/help']:
        help_msg = """
📱 <b>사용 가능한 명령어</b>

• <code>전체</code> / <code>리포트</code> / <code>all</code>
  → 전체 자산 수익률 리포트

• <code>차트</code> / <code>chart</code>
  → 기간별 수익률 차트

• <code>도움말</code> / <code>help</code>
  → 이 메시지 표시

⏰ 자동 리포트 시간:
  09:05, 10:35, 15:40, 17:05, 22:35, 06:05 (KST)
"""
        send_telegram_message(help_msg, chat_id)

def check_messages():
    """새로운 메시지 확인"""
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    
    try:
        r = requests.get(url, params={"offset": last_update_id + 1, "timeout": 10}, timeout=15)
        r.raise_for_status()
        data = r.json()
        
        for u in data.get('result', []):
            last_update_id = u['update_id']
            if 'message' in u and 'text' in u['message']:
                handle_command(u['message']['text'], u['message']['chat']['id'])
    except Exception as e:
        print(f"❌ 메시지 확인 실패: {e}")

def scheduled_report():
    """스케줄된 리포트 전송"""
    print(f"⏰ 정기 리포트 전송 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    handle_command('전체', TELEGRAM_CHAT_ID)

if __name__ == "__main__":
    print("🚀 글로벌 주식 봇 시작!")
    print(f"📱 텔레그램 채팅 ID: {TELEGRAM_CHAT_ID}")
    
    # Flask 서버 시작
    keep_alive()
    print("✅ Flask 서버 시작 완료")
    
    # 시작 메시지 전송
    send_telegram_message("🤖 봇이 시작되었습니다!\n<code>도움말</code> 입력으로 사용법을 확인하세요.")
    
    # 스케줄링 설정 (한국 시간 기준)
    times = ["09:05", "10:35", "15:40", "17:05", "22:35", "06:05"]
    for t in times:
        schedule.every().day.at(t).do(scheduled_report)
    print(f"⏰ 스케줄 설정 완료: {', '.join(times)}")
    
    # 메인 루프
    print("✅ 봇 가동 중... (Ctrl+C로 종료)")
    try:
        while True:
            schedule.run_pending()
            check_messages()
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n👋 봇을 종료합니다.")
        send_telegram_message("🤖 봇이 종료되었습니다.")
