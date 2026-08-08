import os
import sys
import time
import threading
import requests
from datetime import datetime
from flask import Flask
import yfinance as yf
import pandas as pd
import numpy as np
from collections import deque

# ============================================
# CREDENTIALS
# ============================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = "-1003971188413"

print(f"🚀 Starting Trading Bot...")
print(f"📱 Chat ID: {TELEGRAM_CHAT_ID}")

if not TELEGRAM_TOKEN:
    print("❌ NO TOKEN!")
    sys.exit(1)

# ============================================
# FLASK APP
# ============================================

app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Cascade Signal System is Running!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/send')
def send_test():
    result = send_telegram("🤖 Bot is ALIVE! Trading system active!")
    return "✅ Message sent!" if result else "❌ Failed", 500

@app.route('/force-start')
def force_start():
    send_telegram("🚀 Force starting trading bot...")
    check_all_symbols()
    return "✅ Trading bot started! Check Telegram for updates."

# ============================================
# TELEGRAM FUNCTIONS
# ============================================

def send_telegram(message, disable_notification=False):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_notification': disable_notification
        }
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram message sent")
            return True
        print(f"❌ Failed: {response.status_code}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# ============================================
# SYMBOLS
# ============================================

SYMBOLS_CONFIG = {
    'BTC-USD': {'name': 'Bitcoin', 'emoji': '🟢', 'short': 'BTC'},
    'ETH-USD': {'name': 'Ethereum', 'emoji': '🟣', 'short': 'ETH'},
    'SOL-USD': {'name': 'Solana', 'emoji': '🟠', 'short': 'SOL'},
    'PAXG-USD': {'name': 'PAX Gold', 'emoji': '🥇', 'short': 'PAXG'},
    'SI=F': {'name': 'Silver', 'emoji': '🥈', 'short': 'SLV'},
    '^NSEI': {'name': 'Nifty 50', 'emoji': '🇮🇳', 'short': 'NIFTY'}
}

# ============================================
# INDICATORS
# ============================================

def wma(price, period):
    weights = np.arange(1, period + 1)
    def _wma(arr):
        return np.sum(arr * weights) / weights.sum()
    return price.rolling(period).apply(_wma, raw=True)

def calculate_rsi(data, period=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def supertrend(high, low, close, period=14, multiplier=3):
    atr_vals = atr(high, low, close, period)
    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr_vals
    lower_band = hl2 - multiplier * atr_vals
    
    trend = pd.Series(index=close.index, dtype=float)
    trend.iloc[0] = 1 if close.iloc[0] > upper_band.iloc[0] else -1
    
    for i in range(1, len(close)):
        if trend.iloc[i-1] == 1:
            trend.iloc[i] = -1 if close.iloc[i] < lower_band.iloc[i-1] else 1
        else:
            trend.iloc[i] = 1 if close.iloc[i] > upper_band.iloc[i-1] else -1
    
    return trend

def calculate_fast_rsi_wma(data, rsi_period=6, smooth_period=6):
    rsi = calculate_rsi(data, period=rsi_period)
    weights = np.arange(1, smooth_period + 1)
    def _wma(arr):
        return np.sum(arr * weights) / weights.sum()
    smoothed = rsi.rolling(smooth_period).apply(_wma, raw=True)
    return rsi, smoothed

# ============================================
# CHECK ALL SYMBOLS
# ============================================

def check_all_symbols():
    results = {}
    current_prices = {}
    
    print(f"\n📊 Scanning at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    for symbol in SYMBOLS_CONFIG.keys():
        try:
            df = yf.download(symbol, period='1mo', interval='1h', progress=False)
            
            if df is None or len(df) < 30:
                continue
            
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            
            # Calculate indicators
            df['WMA21'] = wma(df['Close'], 21)
            df['WMA51'] = wma(df['Close'], 51)
            df['WMA21_PREV'] = df['WMA21'].shift(1)
            
            df['ST'] = supertrend(df['High'], df['Low'], df['Close'], period=14, multiplier=3)
            df['ST_PREV'] = df['ST'].shift(1)
            
            rsi, rsi_smooth = calculate_fast_rsi_wma(df['Close'], 6, 6)
            df['RSI_FAST'] = rsi
            df['RSI_SMOOTH'] = rsi_smooth
            
            df.dropna(inplace=True)
            
            if len(df) == 0:
                continue
            
            current = df.iloc[-1]
            price = float(current['Close'])
            
            # Stage 1: Fast RSI(6) + WMA(6)
            smooth_rsi = current['RSI_SMOOTH']
            fast_rsi = current['RSI_FAST']
            cross_above = smooth_rsi < fast_rsi and df['RSI_SMOOTH'].iloc[-2] > df['RSI_FAST'].iloc[-2]
            
            # Stage 2: SuperTrend
            st_now = current['ST']
            st_prev = current['ST_PREV']
            st_turn = st_now != st_prev
            
            # Stage 3: Trend
            trend_up = current['WMA21'] > current['WMA51'] and current['WMA21'] > current['WMA21_PREV']
            
            # Determine signal
            signal = "HOLD"
            confidence = 50
            
            if smooth_rsi < 30 and cross_above and trend_up:
                confidence += 30
                if st_now == 1:
                    confidence += 20
                    signal = "BUY"
                else:
                    signal = "CONSIDER BUY"
            elif smooth_rsi > 70 and not cross_above and not trend_up:
                confidence += 30
                if st_now == -1:
                    confidence += 20
                    signal = "SELL"
                else:
                    signal = "CONSIDER SELL"
            
            results[symbol] = signal
            current_prices[symbol] = price
            
        except Exception as e:
            print(f"❌ Error for {symbol}: {e}")
        
        time.sleep(0.3)
    
    # Build message
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = f"<b>🎯 CASCADE SIGNAL SYSTEM</b>\n"
    message += f"⏱ {now}\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"<i>⚡ RSI(6)+WMA6 → SuperTrend → Volume+Trend</i>\n\n"
    
    buy_count = 0
    sell_count = 0
    
    for symbol in SYMBOLS_CONFIG.keys():
        config = SYMBOLS_CONFIG[symbol]
        price = current_prices.get(symbol)
        signal = results.get(symbol, "HOLD")
        
        if price:
            signal_display = "🟢 <b>BUY</b>" if signal == "BUY" else "🔴 <b>SELL</b>" if signal == "SELL" else "🟡 CONSIDER BUY" if signal == "CONSIDER BUY" else "🟡 CONSIDER SELL" if signal == "CONSIDER SELL" else "⏸️ HOLD"
            if signal == "BUY": buy_count += 1
            elif signal == "SELL": sell_count += 1
            
            message += f"\n{config['emoji']} <b>{config['short']}</b>\n"
            message += f"   Price: ${price:.2f}\n"
            message += f"   Signal: {signal_display}\n"
    
    # Market sentiment
    sentiment = buy_count - sell_count
    if sentiment > 1:
        sentiment_text = "🟢 BULLISH"
        emoji = "🚀"
    elif sentiment < -1:
        sentiment_text = "🔴 BEARISH"
        emoji = "📉"
    else:
        sentiment_text = "🟡 NEUTRAL"
        emoji = "⏸️"
    
    message += f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"<b>📊 SENTIMENT: {emoji} {sentiment_text}</b>\n"
    message += f"   Buys: {buy_count} | Sells: {sell_count}\n"
    message += f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"⏱ Next update in 15 minutes\n"
    message += f"🧠 Cascade System: ACTIVE\n"
    
    send_telegram(message)
    return results, current_prices

# ============================================
# BACKGROUND TASK
# ============================================

def trading_loop():
    """Run trading scans every 15 minutes"""
    print("🔄 Trading loop started!")
    time.sleep(10)  # Wait for startup
    
    # Send startup message
    send_telegram("🚀 <b>TRADING BOT STARTED</b>\n\n📊 Monitoring: BTC, ETH, SOL, PAXG, Silver, NIFTY\n⚡ Strategy: RSI(6)+WMA6 → SuperTrend → Volume+Trend")
    
    # Run first scan
    print("📊 Running initial scan...")
    check_all_symbols()
    
    # Then every 15 minutes
    while True:
        time.sleep(900)  # 15 minutes
        print(f"\n🔄 Scheduled scan at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        check_all_symbols()

# ============================================
# START
# ============================================

print("🚀 Starting Trading Bot...")

# Start background thread
thread = threading.Thread(target=trading_loop, daemon=True)
thread.start()
print("✅ Trading loop started")

print("🌐 Flask running on port " + os.environ.get("PORT", "5000"))
