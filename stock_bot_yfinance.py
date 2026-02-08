import os
import yfinance as yf
import requests
import schedule
import time
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
import matplotlib
matplotlib.use('Agg')  # 서버 환경용
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager, rc
import io

# 한글 폰트 설정 (matplotlib)
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

# Render 포트 바인딩 해결을 위한 Flask 서버 설정
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()

# 텔레그램 설정
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8502208649:AAFtvAb9Au9hxeEZzOK-zN70ZTCEDQO-e7s")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "417485629")

# 관심 종목
INTEREST_STOCKS_KR = {
    "005930.KS": "SEC",
    "000660.KS": "HYNIX",
    "005380.KS": "HYUNDAI MOTORS",
    "035420.KS": "NAVER"

}

INTEREST_STOCKS_US = {
    "AAPL": "AAPLE", 
    "TSLA": "TESLA", 
    "NVDA": "NVDIA",
    "GOOGL": "GOOGLE"
}

CRYPTO = {
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Etherium"
}

PRECIOUS_METALS = {
    "GC=F": "GOLD",
    "SI=F": "SILVER"
}

def send_telegram_message(message):
    """텔레그램 텍스트 메시지 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
        print(f"✅ 메시지 전송 성공: {datetime.now()}")
    except Exception as e:
        print(f"❌ Error: {e}")

def send_telegram_photo(image_buffer, caption=""):
    """텔레그램 이미지 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        files = {'photo': ('chart.png', image_buffer, 'image/png')}
        data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            print(f"✅ 이미지 전송 성공: {datetime.now()}")
        else:
            print(f"❌ 이미지 전송 실패: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def get_stock_info(symbol, name, market="US"):
    """주식 정보 조회"""
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="2d")
        if hist.empty:
            return None
        curr = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else curr
        rate = ((curr - prev) / prev) * 100 if prev else 0
        
        if market == "KR":
            return f"🔹 {name}: {curr:,.0f}원 ({rate:+.2f}%)"
        else:
            return f"🔹 {name}: ${curr:.2f} ({rate:+.2f}%)"
    except Exception as e:
        print(f"❌ {name} 오류: {e}")
        return None

def get_crypto_info(symbol, name):
    """암호화폐 정보 조회"""
    try:
        crypto = yf.Ticker(symbol)
        hist = crypto.history(period="2d")
        if hist.empty:
            return None
        curr = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else curr
        rate = ((curr - prev) / prev) * 100 if prev else 0
        
        return f"₿ {name}: ${curr:,.2f} ({rate:+.2f}%)"
    except Exception as e:
        print(f"❌ {name} 오류: {e}")
        return None

def get_metal_info(symbol, name):
    """귀금속 정보 조회"""
    try:
        metal = yf.Ticker(symbol)
        hist = metal.history(period="2d")
        if hist.empty:
            return None
        curr = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2] if len(hist) > 1 else curr
        rate = ((curr - prev) / prev) * 100 if prev else 0
        
        return f"🪙 {name}: ${curr:,.2f}/oz ({rate:+.2f}%)"
    except Exception as e:
        print(f"❌ {name} 오류: {e}")
        return None

def create_price_chart():
    """가격 추세 차트 생성"""
    try:
        print("📊 차트 생성 중...")
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Investment Dashboard - 30 Days Trend', fontsize=16, fontweight='bold')
        
        # 1. 미국 주식 차트
        ax1 = axes[0, 0]
        for symbol, name in INTEREST_STOCKS_US.items():
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(period="1mo")
                if not hist.empty:
                    ax1.plot(hist.index, hist['Close'], label=name, linewidth=2)
            except:
                pass
        ax1.set_title('US Stocks (30 Days)', fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Price (USD)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. 암호화폐 차트
        ax2 = axes[0, 1]
        for symbol, name in CRYPTO.items():
            try:
                crypto = yf.Ticker(symbol)
                hist = crypto.history(period="1mo")
                if not hist.empty:
                    ax2.plot(hist.index, hist['Close'], label=name, linewidth=2)
            except:
                pass
        ax2.set_title('Cryptocurrency (30 Days)', fontweight='bold')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Price (USD)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. 귀금속 차트
        ax3 = axes[1, 0]
        for symbol, name in PRECIOUS_METALS.items():
            try:
                metal = yf.Ticker(symbol)
                hist = metal.history(period="1mo")
                if not hist.empty:
                    ax3.plot(hist.index, hist['Close'], label=name, linewidth=2)
            except:
                pass
        ax3.set_title('Precious Metals (30 Days)', fontweight='bold')
        ax3.set_xlabel('Date')
        ax3.set_ylabel('Price (USD/oz)')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 4. 수익률 비교 막대 그래프
        ax4 = axes[1, 1]
        returns = {}
        
        # 모든 자산의 30일 수익률 계산
        all_assets = {**INTEREST_STOCKS_US, **CRYPTO, **PRECIOUS_METALS}
        for symbol, name in all_assets.items():
            try:
                asset = yf.Ticker(symbol)
                hist = asset.history(period="1mo")
                if len(hist) >= 2:
                    first = hist['Close'].iloc[0]
                    last = hist['Close'].iloc[-1]
                    ret = ((last - first) / first) * 100
                    returns[name] = ret
            except:
                pass
        
        if returns:
            names = list(returns.keys())
            values = list(returns.values())
            colors = ['green' if v > 0 else 'red' for v in values]
            
            bars = ax4.barh(names, values, color=colors, alpha=0.7)
            ax4.set_title('30-Day Returns (%)', fontweight='bold')
            ax4.set_xlabel('Return (%)')
            ax4.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
            ax4.grid(True, alpha=0.3, axis='x')
            
            # 값 표시
            for i, (name, value) in enumerate(zip(names, values)):
                ax4.text(value, i, f' {value:+.1f}%', 
                        va='center', fontsize=9)
        
        plt.tight_layout()
        
        # 이미지를 메모리 버퍼에 저장
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        print("✅ 차트 생성 완료")
        return buf
        
    except Exception as e:
        print(f"❌ 차트 생성 오류: {e}")
        return None

def create_performance_chart():
    """종목별 성과 비교 차트"""
    try:
        print("📊 성과 차트 생성 중...")
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle('Performance Comparison', fontsize=16, fontweight='bold')
        
        # 1주일, 1개월 수익률 계산
        week_returns = {}
        month_returns = {}
        
        all_assets = {**INTEREST_STOCKS_US, **CRYPTO}
        
        for symbol, name in all_assets.items():
            try:
                asset = yf.Ticker(symbol)
                hist = asset.history(period="1mo")
                
                if len(hist) >= 7:
                    week_old = hist['Close'].iloc[-7]
                    current = hist['Close'].iloc[-1]
                    week_ret = ((current - week_old) / week_old) * 100
                    week_returns[name] = week_ret
                
                if len(hist) >= 2:
                    month_old = hist['Close'].iloc[0]
                    current = hist['Close'].iloc[-1]
                    month_ret = ((current - month_old) / month_old) * 100
                    month_returns[name] = month_ret
            except:
                pass
        
        # 1주일 수익률 차트
        if week_returns:
            names = list(week_returns.keys())
            values = list(week_returns.values())
            colors = ['#2ecc71' if v > 0 else '#e74c3c' for v in values]
            
            ax1.bar(range(len(names)), values, color=colors, alpha=0.7)
            ax1.set_xticks(range(len(names)))
            ax1.set_xticklabels(names, rotation=45, ha='right')
            ax1.set_title('7-Day Returns (%)', fontweight='bold')
            ax1.set_ylabel('Return (%)')
            ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax1.grid(True, alpha=0.3, axis='y')
            
            for i, v in enumerate(values):
                ax1.text(i, v, f'{v:+.1f}%', ha='center', 
                        va='bottom' if v > 0 else 'top', fontsize=9)
        
        # 1개월 수익률 차트
        if month_returns:
            names = list(month_returns.keys())
            values = list(month_returns.values())
            colors = ['#3498db' if v > 0 else '#e67e22' for v in values]
            
            ax2.bar(range(len(names)), values, color=colors, alpha=0.7)
            ax2.set_xticks(range(len(names)))
            ax2.set_xticklabels(names, rotation=45, ha='right')
            ax2.set_title('30-Day Returns (%)', fontweight='bold')
            ax2.set_ylabel('Return (%)')
            ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
            ax2.grid(True, alpha=0.3, axis='y')
            
            for i, v in enumerate(values):
                ax2.text(i, v, f'{v:+.1f}%', ha='center', 
                        va='bottom' if v > 0 else 'top', fontsize=9)
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        print("✅ 성과 차트 생성 완료")
        return buf
        
    except Exception as e:
        print(f"❌ 성과 차트 생성 오류: {e}")
        return None

def job():
    """정기 리포트 생성 및 전송"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    report = f"🌍 <b>글로벌 투자 리포트</b> ({now})\n" + "="*30 + "\n\n"
    
    # 1. 한국 주식
    report += "🇰🇷 <b>한국 주식</b>\n"
    for s, n in INTEREST_STOCKS_KR.items():
        info = get_stock_info(s, n, "KR")
        if info:
            report += info + "\n"
    
    # 2. 미국 주식
    report += "\n🇺🇸 <b>미국 주식</b>\n"
    for s, n in INTEREST_STOCKS_US.items():
        info = get_stock_info(s, n, "US")
        if info:
            report += info + "\n"
    
    # 3. 암호화폐
    report += "\n💎 <b>암호화폐</b>\n"
    for s, n in CRYPTO.items():
        info = get_crypto_info(s, n)
        if info:
            report += info + "\n"
        time.sleep(0.5)
    
    # 4. 귀금속
    report += "\n🏆 <b>귀금속</b>\n"
    for s, n in PRECIOUS_METALS.items():
        info = get_metal_info(s, n)
        if info:
            report += info + "\n"
        time.sleep(0.5)
    
    report += "\n" + "="*30
    report += "\n💡 <i>현명한 투자 하세요!</i>"
    
    # 텍스트 리포트 전송
    send_telegram_message(report)
    
    # 차트 전송
    time.sleep(2)
    
    # 1. 가격 추세 차트
    chart1 = create_price_chart()
    if chart1:
        send_telegram_photo(chart1, caption="📊 30일 가격 추세 및 수익률 비교")
        time.sleep(2)
    
    # 2. 성과 비교 차트
    chart2 = create_performance_chart()
    if chart2:
        send_telegram_photo(chart2, caption="📈 7일/30일 수익률 비교")

if __name__ == "__main__":
    print("🚀 봇 가동 시작...")
    
    # Flask 서버 시작
    keep_alive()
    
    # 스케줄 설정
    schedule.every().day.at("06:00").do(job)
    schedule.every().day.at("09:00").do(job)
    schedule.every().day.at("12:00").do(job)
    schedule.every().day.at("15:40").do(job)
    schedule.every().day.at("23:50").do(job)
    
    # 시작 메시지
    send_telegram_message("✅ 봇이 Render 서버에서 성공적으로 실행되었습니다!\n🔔 매일5번리포트와 차트를 보내드립니다.")
    
    print("🤖 봇이 실행 중입니다...")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("👋 봇 종료")
