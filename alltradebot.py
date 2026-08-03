from flask import Flask
import threading
from delta_rest_client import DeltaRestClient
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime
import json
import os
import sys

# ============================================
# CREDENTIALS - UPDATE THESE!
# ============================================
API_KEY = "cWUHyTA848xDdgKCjgtAuNBgebAvil"
API_SECRET = "cWUHyTA848xDdgKCjgtAuNBgebAvil"

# Telegram Bot Token (from BotFather)
TELEGRAM_TOKEN = "8815327869:AAH2kYrE35GvasgmzSpFaRIXUc69bobC1ZI"

# Group Chat ID - Get this using the method above
# IMPORTANT: Group IDs usually start with -100 (negative number)
TELEGRAM_CHAT_ID = "-5028779191"  # REPLACE WITH YOUR ACTUAL GROUP CHAT ID!

# ============================================
# FLASK APP FOR RENDER HEALTH CHECKS
# ============================================
app = Flask(__name__)

@app.route('/')
def home():
    return "BTC SuperTrend Bot is running 24/7!"

@app.route('/health')
def health():
    return "OK", 200

def run_web_server():
    """Run Flask web server in background for Render"""
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ============================================
# TEST TELEGRAM CONNECTION FIRST!
# ============================================
def test_telegram_connection():
    """Test if Telegram connection works"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
        response = requests.get(url)
        if response.status_code == 200:
            bot_info = response.json()
            print(f"✅ Bot connected: @{bot_info['result']['username']}")
            return True
        else:
            print(f"❌ Bot connection failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_group_chat_id():
    """Test if the group chat ID is correct"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': '🔄 Test Message - Bot is working!'
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print(f"✅ Test message sent to group!")
            return True
        else:
            print(f"❌ Failed to send test message: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# ============================================
# INITIALIZE CLIENT
# ============================================
client = DeltaRestClient(
    base_url='https://api.india.delta.exchange',
    api_key=API_KEY,
    api_secret=API_SECRET
)

# ============================================
# SYMBOL CONFIGURATION
# ============================================
SYMBOLS_CONFIG = {
    'BTCUSD': {
        'name': 'Bitcoin',
        'emoji': '🟢',
        'short': 'BTC',
        'stop_loss_pct': 0.03,
        'take_profit_pct': 0.09,
        'st_period': 14,
        'st_multiplier': 3.0,
        'price_change_threshold': 0.5,
        'active': True
    },
    'ETHUSD': {
        'name': 'Ethereum',
        'emoji': '🟣',
        'short': 'ETH',
        'stop_loss_pct': 0.035,
        'take_profit_pct': 0.10,
        'st_period': 12,
        'st_multiplier': 2.8,
        'price_change_threshold': 0.8,
        'active': True
    },
    'PAXGUSD': {
        'name': 'PAX Gold',
        'emoji': '🥇',
        'short': 'PAXG',
        'stop_loss_pct': 0.015,
        'take_profit_pct': 0.05,
        'st_period': 20,
        'st_multiplier': 3.5,
        'price_change_threshold': 0.3,
        'active': True
    },
    'SOLUSD': {
        'name': 'Solana',
        'emoji': '🟠',
        'short': 'SOL',
        'stop_loss_pct': 0.05,
        'take_profit_pct': 0.15,
        'st_period': 10,
        'st_multiplier': 2.5,
        'price_change_threshold': 1.0,
        'active': True
    },
    'SLVONUSD': {
        'name': 'Silver',
        'emoji': '🥈',
        'short': 'SLV',
        'stop_loss_pct': 0.025,
        'take_profit_pct': 0.075,
        'st_period': 16,
        'st_multiplier': 3.2,
        'price_change_threshold': 0.5,
        'active': True
    }
}

ACTIVE_SYMBOLS = [symbol for symbol, config in SYMBOLS_CONFIG.items() if config['active']]

# ============================================
# TELEGRAM FUNCTIONS
# ============================================
def send_telegram(message, disable_notification=False):
    """Send message to Telegram group"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_notification': disable_notification
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("✅ Telegram message sent to group")
            return True
        else:
            print(f"❌ Telegram failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

def get_group_chat_id_manual():
    """Helper function to find your group chat ID"""
    print("\n🔍 Fetching recent messages to find group chat ID...")
    print("Make sure you've sent a message in the group recently!\n")
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get('ok') and data.get('result'):
            print("📋 Found these recent chats:")
            print("=" * 50)
            for update in data['result']:
                if 'message' in update:
                    chat = update['message']['chat']
                    chat_type = chat.get('type', 'unknown')
                    chat_title = chat.get('title', 'Private Chat')
                    chat_id = chat['id']
                    
                    print(f"📱 Type: {chat_type}")
                    print(f"📝 Title/Name: {chat_title}")
                    print(f"🆔 Chat ID: {chat_id}")
                    print("-" * 30)
            print("\n📌 Copy the Chat ID for your group (usually negative number)")
            print(f"   Example: -1001234567890")
            print(f"   Then update TELEGRAM_CHAT_ID in the code")
        else:
            print("\n❌ No recent messages found.")
            print("Please follow these steps:")
            print("1. Add your bot to the group")
            print("2. Send a message in the group (e.g., 'Hello bot')")
            print("3. Run this script again")
    except Exception as e:
        print(f"❌ Error: {e}")

# ============================================
# DATA FETCHING & INDICATORS
# ============================================
def get_candles(symbol, resolution='1h', days=90):
    """Fetch candles for any symbol from Delta Exchange"""
    end = int(time.time())
    start = end - (days * 24 * 60 * 60)
    
    try:
        candles = client.get_candles(
            symbol=symbol,
            resolution=resolution,
            start=start,
            end=end
        )
        
        if not candles or len(candles) == 0:
            print(f"⚠️ No data returned for {symbol}")
            return None
        
        df = pd.DataFrame(candles)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        df.columns = [c.capitalize() for c in df.columns]
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        df = df.sort_index().astype(float)
        
        return df
    except Exception as e:
        print(f"❌ Error fetching data for {symbol}: {e}")
        return None

def wma(price, period):
    """Weighted Moving Average"""
    weights = np.arange(1, period + 1)
    def _wma(arr):
        return np.sum(arr * weights) / weights.sum()
    return price.rolling(period).apply(_wma, raw=True)

def atr(high, low, close, period=14):
    """Average True Range"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def supertrend(high, low, close, period=14, multiplier=3):
    """Supertrend Indicator"""
    atr_vals = atr(high, low, close, period)
    hl2 = (high + low) / 2
    upper_band = hl2 + multiplier * atr_vals
    lower_band = hl2 - multiplier * atr_vals

    trend = pd.Series(index=close.index, dtype=float)
    trend.iloc[0] = 1 if close.iloc[0] > upper_band.iloc[0] else -1

    for i in range(1, len(close)):
        if trend.iloc[i-1] == 1:
            if close.iloc[i] < lower_band.iloc[i-1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = 1
        else:
            if close.iloc[i] > upper_band.iloc[i-1]:
                trend.iloc[i] = 1
            else:
                trend.iloc[i] = -1

    return trend

# ============================================
# CHECK SIGNALS
# ============================================
def check_signal(symbol='BTCUSD', prev_price=None):
    """Check for BUY/SELL signals"""
    config = SYMBOLS_CONFIG.get(symbol)
    if not config or not config['active']:
        return "INACTIVE", None, None

    try:
        df = get_candles(symbol=symbol, resolution='1h', days=90)
        
        if df is None or len(df) < 51:
            return "ERROR", None, None

        df['WMA21'] = wma(df['Close'], 21)
        df['WMA51'] = wma(df['Close'], 51)
        df['WMA21_PREV'] = df['WMA21'].shift(1)
        
        st_period = config.get('st_period', 14)
        st_multiplier = config.get('st_multiplier', 3.0)
        
        df['ST'] = supertrend(df['High'], df['Low'], df['Close'], 
                              period=st_period, multiplier=st_multiplier)
        df['ST_PREV'] = df['ST'].shift(1)
        df.dropna(inplace=True)

        if len(df) == 0:
            return "ERROR", None, None

        current = df.iloc[-1]
        price = current['Close']
        wma21 = current['WMA21']
        wma51 = current['WMA51']
        wma21_prev = current['WMA21_PREV']
        st_now = current['ST']
        st_prev = current['ST_PREV']

        # Check price change
        price_alert = None
        if prev_price is not None:
            change_pct = ((price - prev_price) / prev_price) * 100
            threshold = config.get('price_change_threshold', 0.5)
            if abs(change_pct) >= threshold:
                price_alert = change_pct

        st_just_turned_green = st_now == 1 and st_prev == -1
        st_just_turned_red = st_now == -1 and st_prev == 1
        trend_up = wma21 > wma51 and wma21 > wma21_prev
        trend_down = wma21 < wma51 and wma21 < wma21_prev

        signal = "HOLD"
        if st_just_turned_green and trend_up:
            signal = "BUY"
        elif st_just_turned_red and trend_down:
            signal = "SELL"

        return signal, price, price_alert

    except Exception as e:
        print(f"❌ Error for {symbol}: {e}")
        return "ERROR", None, None

# ============================================
# SEND MARKET UPDATE TO TELEGRAM
# ============================================
def send_market_update():
    """Send comprehensive market update to Telegram"""
    results = {}
    current_prices = {}
    
    print(f"\n📊 Scanning at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    for symbol in ACTIVE_SYMBOLS:
        signal, price, alert = check_signal(symbol)
        results[symbol] = signal
        if price:
            current_prices[symbol] = price
        time.sleep(0.3)
    
    # Build message
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = f"""
📊 <b>Market Update</b> ⏱ {now}
━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    for symbol in ACTIVE_SYMBOLS:
        config = SYMBOLS_CONFIG[symbol]
        price = current_prices.get(symbol)
        signal = results.get(symbol, "HOLD")
        
        if price:
            if signal == "BUY":
                signal_emoji = "🟢 BUY"
            elif signal == "SELL":
                signal_emoji = "🔴 SELL"
            else:
                signal_emoji = "⏸️ HOLD"
            
            message += f"""
{config['emoji']} <b>{symbol}</b>
   Price: ${price:.2f}
   Signal: {signal_emoji}
"""
    
    message += """
━━━━━━━━━━━━━━━━━━━━━━━
⏱ Next update in 15 minutes
🤖 Bot: Active
"""
    
    # Send to Telegram
    send_telegram(message, disable_notification=False)
    return results, current_prices

# ============================================
# MAIN
# ============================================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 MULTI-SYMBOL CRYPTO SIGNAL BOT")
    print("=" * 60)
    
    # Step 1: Test Telegram bot connection
    print("\n📱 Testing Telegram connection...")
    if not test_telegram_connection():
        print("❌ Bot token is invalid. Please check TELEGRAM_TOKEN")
        sys.exit(1)
    
    # Step 2: Check if group chat ID is correct
    print("\n💬 Testing group chat ID...")
    if not test_group_chat_id():
        print("\n❌ Failed to send message to group.")
        print("\n📌 To fix this:")
        print("1. Add your bot to the group")
        print("2. Send a message in the group")
        print("3. Run the get_group_chat_id_manual() function")
        print("4. Copy the chat ID and update TELEGRAM_CHAT_ID")
        print("\n🔍 Would you like to find your group chat ID now?")
        response = input("Type 'y' to find your group ID: ").strip().lower()
        if response == 'y':
            get_group_chat_id_manual()
            print("\n⚠️ Update TELEGRAM_CHAT_ID with your group ID and restart the bot")
            sys.exit(0)
        else:
            sys.exit(1)
    
    # Step 3: Send startup message
    print("\n✅ All good! Starting bot...")
    send_telegram(f"""
✅ <b>Trading Bot Started</b> 🚀

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📊 Strategy: Supertrend + WMA
⏱ Updates: Every 15 Minutes
📈 Monitoring: {', '.join(ACTIVE_SYMBOLS)}

Bot is now active and will send updates here!
    """)
    
    # Step 4: Run initial scan
    print("\n📊 Running initial scan...")
    send_market_update()
    
    # Step 5: Main loop - every 15 minutes
    print(f"\n🤖 Bot is running. Updates will be sent to Telegram every 15 minutes.")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            time.sleep(900)  # 15 minutes
            send_market_update()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        send_telegram("🛑 Bot stopped by user")

# ============================================
# HELPER: Find Group Chat ID (Run this separately)
# ============================================
def find_group_id():
    """Standalone function to find group chat ID"""
    print("\n🔍 Finding Telegram Group Chat ID...")
    print("Make sure you've sent a message in the group recently!")
    print("=" * 50)
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        response = requests.get(url)
        data = response.json()
        
        if data.get('ok') and data.get('result'):
            for update in data['result']:
                if 'message' in update:
                    chat = update['message']['chat']
                    print(f"\n📱 Chat Type: {chat.get('type')}")
                    print(f"📝 Title: {chat.get('title', 'Private Chat')}")
                    print(f"🆔 Chat ID: {chat['id']}")
                    print("-" * 30)
            
            print("\n✅ Copy the Chat ID (for groups, it starts with -100)")
            print("📌 Update TELEGRAM_CHAT_ID with this number")
        else:
            print("\n❌ No recent messages found.")
            print("Steps to fix:")
            print("1. Add your bot to your group")
            print("2. Send a message like 'Hello bot' in the group")
            print("3. Wait 2 seconds")
            print("4. Run this function again")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("="*60)
    print("🚀 BTC SUPERTREND TRADING BOT")
    print("="*60)
    
    # Start web server for Render
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("🌐 Web server started for health checks")
    
    # Check if we need to find group chat ID
    print("\n🔍 Starting bot with Telegram group:", TELEGRAM_CHAT_ID)
    
    # Send startup message
    send_telegram(f"""
✅ <b>BTC SuperTrend Trading Bot Started</b>

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📊 Strategy: SuperTrend + WMA21 + WMA51
⏱ Check Interval: Every 15 minutes
📈 Monitoring: BTCUSD, ETHUSD, PAXGUSD, SOLUSD, SLVONUSD

Bot is now active and monitoring the markets!
    """)
    
    # Run initial check
    print("\n🔍 Running initial signal check...")
    check_all_symbols()
    
    # Main loop - every 15 minutes
    print(f"\n🤖 Bot running. Checks every 15 minutes.")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            time.sleep(900)  # 15 minutes
            check_all_symbols()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped")
        send_telegram("🛑 Bot stopped")
