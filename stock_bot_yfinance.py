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

# matplotlib 설정
import matplotlib
matplotlib.use('Agg')  # 서버 환경용
import matplotlib.pyplot as plt

# Flask 서버
app = Flask(__name__)

@app.route('/')
def home():
    return "Stock Bot is Running! ✅"

@app.route('/health')
def health():
    return "OK", 200

def run_server():
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask 서버 시작: 포트 {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    t = Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(2)

# 텔레그램 설정
TELEGRAM_BOT_TOKEN = "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s"
TELEGRAM_CHAT_ID = "417485629"

# 마지막으로 처리한 메시지 ID
last_update_id = 0

# 관심 종목
STOCKS_KR = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스"
}

STOCKS_US = {
    "AAPL": "애플",
    "TSLA": "테슬라",
    "NVDA": "엔비디아"
}

CRYPTO = {
    "BTC-USD": "비트코인",
    "ETH-USD": "이더리움"
}

METALS = {
    "GC=F": "금",
    "SI=F": "은"
}

def send_message(text, chat_id=None):
    """텔레그램 메시지 전송"""
    if chat_id is None:
        chat_id = TELEGRAM_CHAT_ID
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
        if r.status_code == 200:
            print(f"✅ 메시지 전송 성공")
            return True
        else:
            print(f"❌ 메시지 전송 실패: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ 전송 오류: {e}")
        return False

def send_photo(image_buffer, caption="", chat_id=None):
    """텔레그램 이미지 전송"""
    if chat_id is None:
        chat_id = TELEGRAM_CHAT_ID
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        files = {'photo': ('chart.png', image_buffer, 'image/png')}
        data = {'chat_id': chat_id, 'caption': caption}
        response = requests.post(url, files=files, data=data, timeout=30)
        if response.status_code == 200:
            print(f"✅ 이미지 전송 성공")
            return True
        else:
            print(f"❌ 이미지 전송 실패: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 이미지 전송 오류: {e}")
        return False

def get_price(symbol, name, market):
    """가격 조회"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        
        if hist.empty:
            return None
        
        curr = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else curr
        change = ((curr - prev) / prev * 100) if prev else 0
        
        # 주간 변화
        if len(hist) >= 5:
            week_old = hist['Close'].iloc[0]
            week_change = ((curr - week_old) / week_old * 100)
        else:
            week_change = 0
        
        if market == "KR":
            return {
                'text': f"🔹 {name}: {curr:,.0f}원 ({change:+.1f}%)",
                'detail': f"📊 <b>{name}</b>\n💰 현재가: {curr:,.0f}원\n📈 일간: {change:+.2f}%\n📅 주간: {week_change:+.2f}%"
            }
        elif market == "CRYPTO":
            return {
                'text': f"₿ {name}: ${curr:,.0f} ({change:+.1f}%)",
                'detail': f"📊 <b>{name}</b>\n💰 현재가: ${curr:,.2f}\n📈 일간: {change:+.2f}%\n📅 주간: {week_change:+.2f}%"
            }
        elif market == "METAL":
            return {
                'text': f"🪙 {name}: ${curr:,.2f}/oz ({change:+.1f}%)",
                'detail': f"📊 <b>{name}</b>\n💰 현재가: ${curr:,.2f}/oz\n📈 일간: {change:+.2f}%\n📅 주간: {week_change:+.2f}%"
            }
        else:
            return {
                'text': f"🔹 {name}: ${curr:.2f} ({change:+.1f}%)",
                'detail': f"📊 <b>{name}</b>\n💰 현재가: ${curr:.2f}\n📈 일간: {change:+.2f}%\n📅 주간: {week_change:+.2f}%"
            }
    except Exception as e:
        print(f"❌ {name} 조회 오류: {e}")
        return None

def get_exchange_rate():
    """환율 조회"""
    try:
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            usd_krw = data['usd'].get('krw', 0)
            jpy_rate = data['usd'].get('jpy', 0)
            jpy_krw = (usd_krw / jpy_rate * 100) if jpy_rate else 0
            
            return f"💱 <b>환율</b>\n🇺🇸 USD: {usd_krw:,.2f}원\n🇯🇵 JPY(100): {jpy_krw:,.2f}원"
    except:
        return None

def create_chart():
    """30일 수익률 차트 생성"""
    try:
        print("📊 차트 생성 중...")
        
        # 수익률 계산
        returns = {}
        all_assets = {**STOCKS_KR, **STOCKS_US, **CRYPTO, **METALS}
        
        for symbol, name in all_assets.items():
            try:
                asset = yf.Ticker(symbol)
                hist = asset.history(period="1mo")
                
                if len(hist) >= 2:
                    first = hist['Close'].iloc[0]
                    last = hist['Close'].iloc[-1]
                    ret = ((last - first) / first) * 100
                    returns[name] = ret
                    
            except Exception as e:
                print(f"❌ {name} 차트 데이터 오류: {e}")
                continue
            
            time.sleep(0.2)
        
        if not returns:
            print("❌ 차트 데이터 없음")
            return None
        
        # 차트 생성
        fig, ax = plt.subplots(figsize=(10, 8))
        
        names = list(returns.keys())
        values = list(returns.values())
        colors = ['#2ecc71' if v > 0 else '#e74c3c' for v in values]
        
        # 가로 막대 그래프
        bars = ax.barh(names, values, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)
        
        # 스타일링
        ax.set_xlabel('Return (%)', fontsize=12, fontweight='bold')
        ax.set_title('30-Day Returns', fontsize=16, fontweight='bold', pad=20)
        ax.axvline(x=0, color='black', linestyle='-', linewidth=1)
        ax.grid(True, alpha=0.3, axis='x')
        
        # 값 표시
        for i, (name, value) in enumerate(zip(names, values)):
            ax.text(value, i, f' {value:+.1f}%', 
                   va='center', fontsize=9, fontweight='bold')
        
        plt.tight_layout()
        
        # 이미지를 메모리에 저장
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        
        # 메모리 해제
        plt.close('all')
        gc.collect()
        
        print("✅ 차트 생성 완료")
        return buf
        
    except Exception as e:
        print(f"❌ 차트 생성 오류: {e}")
        plt.close('all')
        gc.collect()
        return None

def create_price_trend_chart(symbol, name, period="1mo"):
    """개별 종목 가격 추세 차트"""
    try:
        print(f"📊 {name} 차트 생성 중...")
        
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        
        if hist.empty:
            return None
        
        # 차트 생성
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 가격 선 그래프
        ax.plot(hist.index, hist['Close'], linewidth=2, color='#3498db', label='Price')
        
        # 스타일링
        ax.set_title(f'{name} - 30 Day Price Trend', fontsize=14, fontweight='bold')
        ax.set_xlabel('Date', fontsize=10)
        ax.set_ylabel('Price', fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # 현재가와 변화율 표시
        current = hist['Close'].iloc[-1]
        first = hist['Close'].iloc[0]
        change = ((current - first) / first) * 100
        
        ax.text(0.02, 0.98, f'Current: {current:.2f}\nChange: {change:+.2f}%',
               transform=ax.transAxes, fontsize=11, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        
        # 이미지 저장
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        
        # 메모리 해제
        plt.close('all')
        gc.collect()
        
        print(f"✅ {name} 차트 완료")
        return buf
        
    except Exception as e:
        print(f"❌ {name} 차트 오류: {e}")
        plt.close('all')
        gc.collect()
        return None

def create_full_report():
    """전체 리포트 생성"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"🌍 <b>글로벌 투자 리포트</b>\n⏰ {now}\n{'='*30}\n\n"
    
    # 한국 주식
    msg += "🇰🇷 <b>한국 주식</b>\n"
    for symbol, name in STOCKS_KR.items():
        info = get_price(symbol, name, "KR")
        if info:
            msg += info['text'] + "\n"
        time.sleep(0.3)
    
    # 미국 주식
    msg += "\n🇺🇸 <b>미국 주식</b>\n"
    for symbol, name in STOCKS_US.items():
        info = get_price(symbol, name, "US")
        if info:
            msg += info['text'] + "\n"
        time.sleep(0.3)
    
    # 암호화폐
    msg += "\n💎 <b>암호화폐</b>\n"
    for symbol, name in CRYPTO.items():
        info = get_price(symbol, name, "CRYPTO")
        if info:
            msg += info['text'] + "\n"
        time.sleep(0.3)
    
    # 귀금속
    msg += "\n🏆 <b>귀금속</b>\n"
    for symbol, name in METALS.items():
        info = get_price(symbol, name, "METAL")
        if info:
            msg += info['text'] + "\n"
        time.sleep(0.3)
    
    # 환율
    exchange = get_exchange_rate()
    if exchange:
        msg += "\n" + exchange + "\n"
    
    msg += f"\n{'='*30}\n💡 현명한 투자 하세요!"
    return msg

def handle_command(text, chat_id):
    """명령어 처리"""
    text = text.lower().strip()
    print(f"📩 명령어: {text}")
    
    # 도움말
    if text in ['/start', '/help', '도움말', 'help']:
        help_msg = (
            "🤖 <b>주식 알림 봇 명령어</b>\n\n"
            "📊 <b>실시간 조회</b>\n"
            "전체 - 전체 리포트\n"
            "한국 - 한국 주식\n"
            "미국 - 미국 주식\n"
            "코인 - 암호화폐\n"
            "금속 - 귀금속\n"
            "환율 - 환율 정보\n\n"
            "📈 <b>차트</b>\n"
            "차트 - 30일 수익률 차트\n"
            "삼성차트 - 삼성전자 추세\n"
            "애플차트 - 애플 추세\n"
            "비트차트 - 비트코인 추세\n\n"
            "💰 <b>개별 종목</b>\n"
            "삼성 - 삼성전자 상세\n"
            "애플 - 애플 상세\n"
            "테슬라 - 테슬라 상세\n"
            "비트 - 비트코인 상세\n\n"
            "⏰ <b>자동 알림</b>\n"
            "매일 09:00, 15:40 자동 전송"
        )
        send_message(help_msg, chat_id)
        return
    
    # 전체 리포트
    if text in ['전체', '리포트', 'all']:
        send_message("📊 리포트 생성 중...", chat_id)
        msg = create_full_report()
        send_message(msg, chat_id)
        return
    
    # 수익률 차트
    if text in ['차트', 'chart', '수익률']:
        send_message("📊 차트 생성 중... (30초 소요)", chat_id)
        chart = create_chart()
        if chart:
            send_photo(chart, caption="📊 30일 수익률 비교", chat_id=chat_id)
        else:
            send_message("❌ 차트 생성 실패", chat_id)
        return
    
    # 개별 종목 차트
    if '삼성차트' in text or '삼성 차트' in text:
        send_message("📊 삼성전자 차트 생성 중...", chat_id)
        chart = create_price_trend_chart("005930.KS", "삼성전자")
        if chart:
            send_photo(chart, caption="📈 삼성전자 30일 추세", chat_id=chat_id)
        else:
            send_message("❌ 차트 생성 실패", chat_id)
        return
    
    if '애플차트' in text or '애플 차트' in text:
        send_message("📊 애플 차트 생성 중...", chat_id)
        chart = create_price_trend_chart("AAPL", "애플")
        if chart:
            send_photo(chart, caption="📈 애플 30일 추세", chat_id=chat_id)
        else:
            send_message("❌ 차트 생성 실패", chat_id)
        return
    
    if '테슬라차트' in text or '테슬라 차트' in text:
        send_message("📊 테슬라 차트 생성 중...", chat_id)
        chart = create_price_trend_chart("TSLA", "테슬라")
        if chart:
            send_photo(chart, caption="📈 테슬라 30일 추세", chat_id=chat_id)
        else:
            send_message("❌ 차트 생성 실패", chat_id)
        return
    
    if '비트차트' in text or '비트 차트' in text or '비트코인차트' in text:
        send_message("📊 비트코인 차트 생성 중...", chat_id)
        chart = create_price_trend_chart("BTC-USD", "비트코인")
        if chart:
            send_photo(chart, caption="📈 비트코인 30일 추세", chat_id=chat_id)
        else:
            send_message("❌ 차트 생성 실패", chat_id)
        return
    
    # 한국 주식
    if text in ['한국', '코스피', 'kr']:
        msg = "🇰🇷 <b>한국 주식</b>\n"
        for symbol, name in STOCKS_KR.items():
            info = get_price(symbol, name, "KR")
            if info:
                msg += info['text'] + "\n"
        send_message(msg, chat_id)
        return
    
    # 미국 주식
    if text in ['미국', 'us']:
        msg = "🇺🇸 <b>미국 주식</b>\n"
        for symbol, name in STOCKS_US.items():
            info = get_price(symbol, name, "US")
            if info:
                msg += info['text'] + "\n"
        send_message(msg, chat_id)
        return
    
    # 암호화폐
    if text in ['암호화폐', '코인', 'crypto']:
        msg = "💎 <b>암호화폐</b>\n"
        for symbol, name in CRYPTO.items():
            info = get_price(symbol, name, "CRYPTO")
            if info:
                msg += info['text'] + "\n"
        send_message(msg, chat_id)
        return
    
    # 귀금속
    if text in ['귀금속', '금속', 'metal']:
        msg = "🏆 <b>귀금속</b>\n"
        for symbol, name in METALS.items():
            info = get_price(symbol, name, "METAL")
            if info:
                msg += info['text'] + "\n"
        send_message(msg, chat_id)
        return
    
    # 환율
    if text in ['환율', 'exchange']:
        exchange = get_exchange_rate()
        if exchange:
            send_message(exchange, chat_id)
        else:
            send_message("❌ 환율 조회 실패", chat_id)
        return
    
    # 개별 종목
    if '삼성' in text:
        info = get_price("005930.KS", "삼성전자", "KR")
        if info:
            send_message(info['detail'], chat_id)
        return
    
    if 'sk' in text or '하이닉스' in text:
        info = get_price("000660.KS", "SK하이닉스", "KR")
        if info:
            send_message(info['detail'], chat_id)
        return
    
    if '애플' in text or 'apple' in text or 'aapl' in text:
        info = get_price("AAPL", "애플", "US")
        if info:
            send_message(info['detail'], chat_id)
        return
    
    if '테슬라' in text or 'tesla' in text or 'tsla' in text:
        info = get_price("TSLA", "테슬라", "US")
        if info:
            send_message(info['detail'], chat_id)
        return
    
    if '엔비디아' in text or 'nvidia' in text or 'nvda' in text:
        info = get_price("NVDA", "엔비디아", "US")
        if info:
            send_message(info['detail'], chat_id)
        return
    
    if '비트' in text or 'btc' in text or 'bitcoin' in text:
        info = get_price("BTC-USD", "비트코인", "CRYPTO")
        if info:
            send_message(info['detail'], chat_id)
        return
    
    if '이더' in text or 'eth' in text or 'ethereum' in text:
        info = get_price("ETH-USD", "이더리움", "CRYPTO")
        if info:
            send_message(info['detail'], chat_id)
        return
    
    if text in ['금', 'gold']:
        info = get_price("GC=F", "금", "METAL")
        if info:
            send_message(info['detail'], chat_id)
        return
    
    if text in ['은', 'silver']:
        info = get_price("SI=F", "은", "METAL")
        if info:
            send_message(info['detail'], chat_id)
        return
    
    # 알 수 없는 명령어
    send_message(
        "❓ 알 수 없는 명령어입니다.\n\n"
        "💡 <b>도움말</b> 또는 <b>help</b>를 입력하세요!",
        chat_id
    )

def check_messages():
    """새 메시지 확인 (폴링)"""
    global last_update_id
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {
        "offset": last_update_id + 1,
        "timeout": 10
    }
    
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            
            if data['ok'] and data['result']:
                for update in data['result']:
                    update_id = update['update_id']
                    
                    if 'message' in update:
                        message = update['message']
                        chat_id = message['chat']['id']
                        
                        if 'text' in message:
                            text = message['text']
                            handle_command(text, chat_id)
                    
                    last_update_id = max(last_update_id, update_id)
    except Exception as e:
        print(f"❌ 메시지 확인 오류: {e}")

def scheduled_job():
    """정기 작업"""
    print(f"\n📊 정기 리포트: {datetime.now().strftime('%H:%M')}")
    msg = create_full_report()
    send_message(msg)
    print("✅ 정기 리포트 완료\n")

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 글로벌 투자 알림 봇 (차트 기능 포함)")
    print("="*50 + "\n")
    
    # Flask 시작
    print("1️⃣ Flask 서버 시작...")
    keep_alive()
    print("✅ 완료\n")
    
    # 스케줄 설정
    print("2️⃣ 스케줄 설정...")
    schedule.every().day.at("06:00").do(job)
    schedule.every().day.at("09:00").do(job)
    schedule.every().day.at("11:30").do(job)
    schedule.every().day.at("13:30").do(job)
    schedule.every().day.at("15:40").do(job)
    schedule.every().day.at("20:40").do(job)
    schedule.every().day.at("22:30").do(job)
    print("✅ 완료 (06:00, 09:00, 11:30, 13:30, 15:40, 20:40, 22:30)\n")
    
    # 시작 알림
    print("3️⃣ 시작 알림...")
    send_message(
        "✅ <b>봇 시작! (차트 기능 포함)</b>\n\n"
        "💬 <b>명령어:</b>\n"
        "• 전체 - 전체 리포트\n"
        "• 차트 - 30일 수익률 차트\n"
        "• 삼성차트 - 삼성전자 추세\n"
        "• 도움말 - 전체 명령어\n\n"
        "⏰ <b>자동 알림:</b> 09:00, 15:40"
    )
    print("✅ 완료\n")
    
    print("="*50)
    print("🤖 봇 실행 중 (5초마다 메시지 확인)")
    print("📊 차트 기능 활성화")
    print("="*50 + "\n")
    
    # 메인 루프
    try:
        while True:
            schedule.run_pending()
            check_messages()
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n👋 봇 종료")
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        send_message(f"🚨 봇 오류: {str(e)}")
