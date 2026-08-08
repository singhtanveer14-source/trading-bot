import os
import sys
import time
import threading
import requests
import urllib3
from datetime import datetime
from flask import Flask
import yfinance as yf
import pandas as pd
import numpy as np
from collections import deque

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================
# LOAD ENVIRONMENT VARIABLES
# ============================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-5028779191")

print(f"🔑 TELEGRAM_TOKEN: {'✅ Found' if TELEGRAM_TOKEN else '❌ Missing'}")
print(f"📱 TELEGRAM_CHAT_ID: {TELEGRAM_CHAT_ID}")

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN not found!")
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

@app.route('/test-telegram')
def test_telegram():
    """Test endpoint to manually trigger a Telegram message"""
    print("🧪 Test endpoint called!")
    result = send_telegram("🧪 Test message from bot! ✅")
    if result:
        return "✅ Test message sent!"
    else:
        return "❌ Failed", 500

@app.route('/force-start')
def force_start():
    """Force the bot to send messages immediately"""
    print("🚀 Force start called!")
    
    # Send test message
    test_result = send_telegram("🚀 Bot is active! Testing connection...")
    if test_result:
        # Send startup message
        startup = f"""
✅ <b>BOT STARTED</b> 🎯

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📊 Monitoring: BTC, ETH, SOL, PAXG, Silver, NIFTY
🧠 Strategy: RSI(6)+WMA6 → SuperTrend → Volume+Trend
📱 Alerts every 15 minutes

Bot is active! 🧠
        """
        send_telegram(startup)
        
        # Run a scan
        print("📊 Running scan...")
        check_all_symbols()
        
        return "✅ Bot started! Check Telegram."
    else:
        return "❌ Test failed. Check logs.", 500

@app.route('/status')
def status():
    """Check bot status"""
    return {
        'status': 'running',
        'telegram_token': '✅ Set' if TELEGRAM_TOKEN else '❌ Missing',
        'chat_id': TELEGRAM_CHAT_ID,
        'active_symbols': len(ACTIVE_SYMBOLS)
    }

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
        
        print(f"📤 Sending to Telegram...")
        response = requests.post(url, data=payload, timeout=30, verify=False)
        
        print(f"📡 Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                print("✅ Message sent!")
                return True
        
        print(f"❌ Failed: {response.text[:200]}")
        return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# ============================================
# SYMBOL CONFIGURATION
# ============================================

SYMBOLS_CONFIG = {
    'BTC-USD': {'name': 'Bitcoin', 'emoji': '🟢', 'short': 'BTC', 'st_period': 14, 'st_multiplier': 3.0, 'active': True},
    'ETH-USD': {'name': 'Ethereum', 'emoji': '🟣', 'short': 'ETH', 'st_period': 12, 'st_multiplier': 2.8, 'active': True},
    'SOL-USD': {'name': 'Solana', 'emoji': '🟠', 'short': 'SOL', 'st_period': 10, 'st_multiplier': 2.5, 'active': True},
    'PAXG-USD': {'name': 'PAX Gold', 'emoji': '🥇', 'short': 'PAXG', 'st_period': 20, 'st_multiplier': 3.5, 'active': True},
    'SI=F': {'name': 'Silver', 'emoji': '🥈', 'short': 'SLV', 'st_period': 16, 'st_multiplier': 3.2, 'active': True},
    '^NSEI': {'name': 'Nifty 50', 'emoji': '🇮🇳', 'short': 'NIFTY', 'st_period': 14, 'st_multiplier': 3.0, 'active': True}
}

ACTIVE_SYMBOLS = [symbol for symbol, config in SYMBOLS_CONFIG.items() if config['active']]

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

# ============================================
# SIGNAL ENGINE
# ============================================

def check_all_symbols():
    results = {}
    current_prices = {}
    
    print(f"\n📊 Scanning at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    for symbol in ACTIVE_SYMBOLS:
        try:
            config = SYMBOLS_CONFIG[symbol]
            df = yf.download(symbol, period='1mo', interval='1h', progress=False)
            
            if df is None or len(df) < 30:
                continue
            
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            
            st_period = config.get('st_period', 14)
            st_multiplier = config.get('st_multiplier', 3.0)
            
            df['ST'] = supertrend(df['High'], df['Low'], df['Close'],
                                 period=st_period, multiplier=st_multiplier)
            df['ST_PREV'] = df['ST'].shift(1)
            df.dropna(inplace=True)
            
            if len(df) == 0:
                continue
            
            current = df.iloc[-1]
            price = float(current['Close'])
            st_now = current['ST']
            st_prev = current['ST_PREV']
            
            signal = "HOLD"
            if st_now == 1 and st_prev == -1:
                signal = "BUY"
            elif st_now == -1 and st_prev == 1:
                signal = "SELL"
            
            results[symbol] = signal
            current_prices[symbol] = price
            
        except Exception as e:
            print(f"❌ Error for {symbol}: {e}")
        
        time.sleep(0.3)
    
    # Build message
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = f"<b>📊 MARKET UPDATE</b>\n⏱ {now}\n━━━━━━━━━━━━━━━━━━\n"
    
    for symbol in ACTIVE_SYMBOLS:
        config = SYMBOLS_CONFIG[symbol]
        price = current_prices.get(symbol)
        signal = results.get(symbol, "HOLD")
        
        if price:
            signal_emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "⏸️"
            message += f"\n{config['emoji']} {config['short']}\n"
            message += f"   Price: ${price:.2f}\n"
            message += f"   Signal: {signal_emoji} {signal}\n"
    
    message += "\n━━━━━━━━━━━━━━━━━━\n"
    message += f"⏱ Next update in 15 minutes\n"
    
    print("📤 Sending market update...")
    send_telegram(message)
    return results, current_prices

# ============================================
# BACKGROUND TASK
# ============================================

def background_task():
    """Simple background task that runs every 15 minutes"""
    print("🔄 Background task started!")
    
    # Wait a bit for the server to fully start
    time.sleep(5)
    
    # Send initial message
    print("📤 Sending initial message...")
    send_telegram("🚀 Bot is online! Sending first update...")
    time.sleep(2)
    
    # Run first scan
    print("📊 Running first scan...")
    check_all_symbols()
    
    # Then run every 15 minutes
    while True:
        time.sleep(900)  # 15 minutes
        print(f"\n🔄 Running scheduled scan at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        check_all_symbols()

# ============================================
# START THE BACKGROUND THREAD
# ============================================

print("🚀 Starting background task...")
thread = threading.Thread(target=background_task, daemon=True)
thread.start()
print("✅ Background task started")

print("🌐 Flask server starting...")
