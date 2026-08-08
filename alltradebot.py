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
# LOAD ENVIRONMENT VARIABLES
# ============================================

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

if not os.getenv("TELEGRAM_TOKEN"):
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip().strip('"').strip("'")
    except:
        pass

# ============================================
# CREDENTIALS
# ============================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-5028779191")

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN not found in environment variables!")
    print("Please set TELEGRAM_TOKEN in Render Environment settings")
    sys.exit(1)

# ============================================
# FLASK APP
# ============================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Cascade Signal System Active"

@app.route('/health')
def health():
    return "OK", 200

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ============================================
# TELEGRAM FUNCTIONS
# ============================================

def test_telegram_connection():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                print(f"✅ Bot connected: @{data['result']['username']}")
                return True
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_group_chat_id():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': '🔄 Bot is starting up...'
        }
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Test message sent to group!")
            return True
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

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
        return False
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

# ============================================
# SYMBOL CONFIGURATION
# ============================================

SYMBOLS_CONFIG = {
    'BTC-USD': {
        'name': 'Bitcoin', 'emoji': '🟢', 'short': 'BTC',
        'st_period': 14, 'st_multiplier': 3.0,
        'fast_rsi_period': 6, 'fast_rsi_smooth': 6,
        'price_change_threshold': 0.5,
        'active': True
    },
    'ETH-USD': {
        'name': 'Ethereum', 'emoji': '🟣', 'short': 'ETH',
        'st_period': 12, 'st_multiplier': 2.8,
        'fast_rsi_period': 6, 'fast_rsi_smooth': 6,
        'price_change_threshold': 0.8,
        'active': True
    },
    'SOL-USD': {
        'name': 'Solana', 'emoji': '🟠', 'short': 'SOL',
        'st_period': 10, 'st_multiplier': 2.5,
        'fast_rsi_period': 6, 'fast_rsi_smooth': 6,
        'price_change_threshold': 1.0,
        'active': True
    },
    'PAXG-USD': {
        'name': 'PAX Gold', 'emoji': '🥇', 'short': 'PAXG',
        'st_period': 20, 'st_multiplier': 3.5,
        'fast_rsi_period': 6, 'fast_rsi_smooth': 6,
        'price_change_threshold': 0.3,
        'active': True
    },
    'SI=F': {
        'name': 'Silver', 'emoji': '🥈', 'short': 'SLV',
        'st_period': 16, 'st_multiplier': 3.2,
        'fast_rsi_period': 6, 'fast_rsi_smooth': 6,
        'price_change_threshold': 0.5,
        'active': True
    },
    '^NSEI': {
        'name': 'Nifty 50', 'emoji': '🇮🇳', 'short': 'NIFTY',
        'st_period': 14, 'st_multiplier': 3.0,
        'fast_rsi_period': 6, 'fast_rsi_smooth': 6,
        'price_change_threshold': 0.4,
        'active': True
    }
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

def calculate_fast_rsi_wma(data, rsi_period=6, smooth_period=6):
    rsi = calculate_rsi(data, period=rsi_period)
    weights = np.arange(1, smooth_period + 1)
    def _wma(arr):
        return np.sum(arr * weights) / weights.sum()
    smoothed = rsi.rolling(smooth_period).apply(_wma, raw=True)
    return rsi, smoothed

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

def calculate_volume_profile(volume, period=20):
    avg_volume = volume.rolling(window=period).mean()
    volume_ratio = volume / avg_volume
    return avg_volume, volume_ratio

# ============================================
# SIGNAL ENGINE
# ============================================

class SignalEngine:
    def __init__(self):
        self.signal_history = {symbol: deque(maxlen=20) for symbol in ACTIVE_SYMBOLS}
        self.price_history = {symbol: deque(maxlen=30) for symbol in ACTIVE_SYMBOLS}
        self.trade_count = {symbol: 0 for symbol in ACTIVE_SYMBOLS}
        self.last_price = {symbol: None for symbol in ACTIVE_SYMBOLS}
    
    def check_signal(self, symbol):
        config = SYMBOLS_CONFIG.get(symbol)
        if not config or not config['active']:
            return "INACTIVE", None, None
        
        try:
            df = yf.download(symbol, period='3mo', interval='1h',
                           progress=False, auto_adjust=True)
            
            if df is None or len(df) < 51:
                return "ERROR", None, None
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna().astype(float)
            
            st_period = config.get('st_period', 14)
            st_multiplier = config.get('st_multiplier', 3.0)
            
            df['WMA21'] = wma(df['Close'], 21)
            df['WMA51'] = wma(df['Close'], 51)
            df['WMA21_PREV'] = df['WMA21'].shift(1)
            
            df['ST'] = supertrend(df['High'], df['Low'], df['Close'],
                                 period=st_period, multiplier=st_multiplier)
            df['ST_PREV'] = df['ST'].shift(1)
            
            rsi_period = config.get('fast_rsi_period', 6)
            smooth_period = config.get('fast_rsi_smooth', 6)
            df['RSI_FAST'], df['RSI_SMOOTH'] = calculate_fast_rsi_wma(
                df['Close'], rsi_period, smooth_period
            )
            
            df['VOL_AVG'], df['VOL_RATIO'] = calculate_volume_profile(df['Volume'])
            
            df.dropna(inplace=True)
            
            if len(df) == 0:
                return "ERROR", None, None
            
            current = df.iloc[-1]
            price = float(current['Close'])
            
            # Stage 1: Fast RSI(6) + WMA(6)
            fast_rsi = current['RSI_FAST']
            smooth_rsi = current['RSI_SMOOTH']
            
            if len(df) > 1:
                rsi_smooth_prev = df['RSI_SMOOTH'].iloc[-2]
                fast_rsi_prev = df['RSI_FAST'].iloc[-2]
                cross_above = smooth_rsi < fast_rsi and rsi_smooth_prev > fast_rsi_prev
                cross_below = smooth_rsi > fast_rsi and rsi_smooth_prev < fast_rsi_prev
            else:
                cross_above = False
                cross_below = False
            
            early_signal = "HOLD"
            stage1_bullish = smooth_rsi < 30 and cross_above and price > current['WMA21']
            stage1_bearish = smooth_rsi > 70 and cross_below and price < current['WMA21']
            
            if stage1_bullish:
                early_signal = "EARLY_BUY"
            elif stage1_bearish:
                early_signal = "EARLY_SELL"
            
            # Stage 2: SuperTrend
            st_now = current['ST']
            stage2_bullish = st_now == 1
            stage2_bearish = st_now == -1
            
            # Stage 3: Volume + Trend
            volume_surge = current['VOL_RATIO'] > 1.2
            trend_up = current['WMA21'] > current['WMA51'] and current['WMA21'] > current['WMA21_PREV']
            trend_down = current['WMA21'] < current['WMA51'] and current['WMA21'] < current['WMA21_PREV']
            
            # Confidence
            confidence = 50
            if stage1_bullish:
                confidence += 20
            elif stage1_bearish:
                confidence -= 20
            
            if stage2_bullish:
                confidence += 20
            elif stage2_bearish:
                confidence -= 20
            
            if volume_surge:
                confidence += 10
            if trend_up:
                confidence += 5
            elif trend_down:
                confidence -= 5
            
            confidence = max(0, min(100, confidence))
            
            # Primary signal
            primary_signal = "HOLD"
            
            if stage1_bullish and stage2_bullish and volume_surge and confidence >= 70:
                primary_signal = "STRONG_BUY"
            elif stage1_bullish and stage2_bullish and confidence >= 60:
                primary_signal = "BUY"
            elif stage1_bullish and confidence >= 50:
                primary_signal = "CONSIDER_BUY"
            elif stage1_bearish and stage2_bearish and volume_surge and confidence >= 70:
                primary_signal = "STRONG_SELL"
            elif stage1_bearish and stage2_bearish and confidence >= 60:
                primary_signal = "SELL"
            elif stage1_bearish and confidence >= 50:
                primary_signal = "CONSIDER_SELL"
            
            # Price alert
            price_alert = None
            prev_price = self.last_price.get(symbol)
            if prev_price is not None:
                change_pct = ((price - prev_price) / prev_price) * 100
                threshold = config.get('price_change_threshold', 0.5)
                if abs(change_pct) >= threshold:
                    price_alert = change_pct
            
            self.signal_history[symbol].append(primary_signal)
            self.price_history[symbol].append(price)
            self.last_price[symbol] = price
            
            if primary_signal in ['STRONG_BUY', 'BUY', 'STRONG_SELL', 'SELL']:
                self.trade_count[symbol] += 1
            
            return primary_signal, price, price_alert
            
        except Exception as e:
            print(f"❌ Error for {symbol}: {e}")
            return "ERROR", None, None

# ============================================
# CHECK ALL SYMBOLS
# ============================================

def check_all_symbols():
    """Check all symbols and send results to Telegram"""
    engine = SignalEngine()
    results = {}
    current_prices = {}
    
    print(f"\n📊 Scanning at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    for symbol in ACTIVE_SYMBOLS:
        signal, price, alert = engine.check_signal(symbol)
        results[symbol] = signal
        if price:
            current_prices[symbol] = price
        time.sleep(0.3)
    
    # Build message
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = f"<b>🎯 CASCADE SIGNAL SYSTEM</b>\n"
    message += f"⏱ {now}\n"
    message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"<i>⚡ RSI(6)+WMA6 → 🔵 SuperTrend → 📊 Volume+Trend</i>\n\n"
    
    buy_count = 0
    sell_count = 0
    
    for symbol in ACTIVE_SYMBOLS:
        config = SYMBOLS_CONFIG[symbol]
        price = current_prices.get(symbol)
        signal = results.get(symbol, "HOLD")
        
        if price:
            if signal in ["STRONG_BUY", "BUY"]:
                signal_display = "🟢 <b>BUY</b>"
                buy_count += 1
            elif signal in ["STRONG_SELL", "SELL"]:
                signal_display = "🔴 <b>SELL</b>"
                sell_count += 1
            elif signal == "CONSIDER_BUY":
                signal_display = "🟡 CONSIDER BUY"
                buy_count += 0.5
            elif signal == "CONSIDER_SELL":
                signal_display = "🟡 CONSIDER SELL"
                sell_count += 0.5
            else:
                signal_display = "⏸️ HOLD"
            
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
    message += f"   Buys: {buy_count:.1f} | Sells: {sell_count:.1f}\n"
    
    message += f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"⏱ Next update in 15 minutes\n"
    message += f"🧠 Cascade System: ACTIVE\n"
    
    send_telegram(message)
    return results, current_prices

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 CASCADE SIGNAL SYSTEM")
    print("⚡ Fast RSI(6)+WMA6 → SuperTrend → Volume+Trend")
    print("🎯 Multi-Timeframe Analysis Active")
    print("=" * 60)
    
    # Start web server
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("🌐 Web server started for health checks")
    
    # Test connections
    print("\n📱 Testing Telegram connection...")
    if not test_telegram_connection():
        print("❌ Failed to connect to Telegram")
        sys.exit(1)
    
    print("\n💬 Testing group chat ID...")
    if not test_group_chat_id():
        print("❌ Failed to send test message")
        sys.exit(1)
    
    print("\n✅ All good! Starting bot...")
    
    # Send startup message
    startup_msg = f"""
✅ <b>CASCADE SIGNAL SYSTEM STARTED</b> 🎯

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
⚡ <b>Signal Cascade:</b>
   Stage 1: <b>Fast RSI(6) + WMA(6)</b> (Early Signal)
   Stage 2: <b>SuperTrend</b> (Confirmation)
   Stage 3: <b>Volume + Trend</b> (Final Filter)

📊 <b>Monitoring:</b> {', '.join(SYMBOLS_CONFIG[s]['short'] for s in ACTIVE_SYMBOLS)}
🎯 <b>Signal Types:</b> EARLY → CONSIDER → BUY/SELL → STRONG

Bot is now active! 🧠
    """
    send_telegram(startup_msg)
    
    print("\n📊 Running initial scan...")
    check_all_symbols()
    
    print("\n🤖 Bot is running. Updates will be sent to Telegram every 15 minutes.")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            time.sleep(900)  # 15 minutes
            check_all_symbols()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        send_telegram("🛑 Bot stopped by user")
