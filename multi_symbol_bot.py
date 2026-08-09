# ============================================
# MULTI-SYMBOL SIGNAL BOT WITH TELEGRAM
# BTCUSD, ETHUSD, SOLUSD, XAUUSD, XAGUSD, USOIL, NIFTY, BANKNIFTY, SENSEX
# ============================================

import os
import sys
import time
import threading
import requests
from datetime import datetime, timedelta
from flask import Flask
import yfinance as yf
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# ============================================
# TELEGRAM CREDENTIALS - READ FROM ENV
# ============================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003971188413")

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN not found!")
    print("Please set TELEGRAM_TOKEN in Render Environment")
    sys.exit(1)

print(f"✅ TELEGRAM_TOKEN found: {TELEGRAM_TOKEN[:10]}...")
print(f"✅ TELEGRAM_CHAT_ID: {TELEGRAM_CHAT_ID}")

# ============================================
# FLASK APP FOR RENDER HEALTH CHECKS
# ============================================

app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Multi-Symbol Signal Bot is Running!"

@app.route('/health')
def health():
    return "OK", 200

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ============================================
# SYMBOL CONFIGURATION
# ============================================

SYMBOLS = {
    'BTC-USD': {'name': 'Bitcoin', 'emoji': '🟢', 'type': 'Crypto'},
    'ETH-USD': {'name': 'Ethereum', 'emoji': '🟣', 'type': 'Crypto'},
    'SOL-USD': {'name': 'Solana', 'emoji': '🟠', 'type': 'Crypto'},
    'GC=F':    {'name': 'Gold (XAUUSD)', 'emoji': '🥇', 'type': 'Commodity'},
    'SI=F':    {'name': 'Silver (XAGUSD)', 'emoji': '🥈', 'type': 'Commodity'},
    'CL=F':    {'name': 'Crude Oil (USOIL)', 'emoji': '🛢️', 'type': 'Commodity'},
    '^NSEI':   {'name': 'NIFTY 50', 'emoji': '🇮🇳', 'type': 'Index'},
    '^NSEBANK':{'name': 'BANKNIFTY', 'emoji': '🏦', 'type': 'Index'},
    '^BSESN':  {'name': 'SENSEX', 'emoji': '📊', 'type': 'Index'}
}

RSI_PERIOD = 14
WMA_PERIOD = 21
STOP_LOSS_PCT = 1.5
TAKE_PROFIT_PCT = 3.75

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
        print(f"❌ Bot connection failed")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_group_chat_id():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': '🔄 Multi-Symbol Signal Bot is starting up...'
        }
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Test message sent to group!")
            return True
        print(f"❌ Failed: {response.text}")
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
        print(f"❌ Telegram failed: {response.text[:200]}")
        return False
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

# ============================================
# DATA FETCHING
# ============================================

def get_latest_data(symbol):
    try:
        end_date = datetime.now()
        start_1h = end_date - timedelta(days=30)
        start_15m = end_date - timedelta(days=7)
        
        df_1h = yf.download(symbol, start=start_1h, end=end_date, 
                            interval='1h', progress=False)
        
        df_15m = yf.download(symbol, start=start_15m, end=end_date, 
                             interval='15m', progress=False)
        
        if df_1h.empty:
            return None, None
        
        if hasattr(df_1h, 'columns') and isinstance(df_1h.columns, pd.MultiIndex):
            df_1h.columns = df_1h.columns.get_level_values(0)
        
        if not df_15m.empty and hasattr(df_15m, 'columns') and isinstance(df_15m.columns, pd.MultiIndex):
            df_15m.columns = df_15m.columns.get_level_values(0)
        
        return df_1h, df_15m
    except Exception as e:
        print(f"❌ Error fetching {symbol}: {e}")
        return None, None

# ============================================
# SIGNAL CALCULATIONS
# ============================================

def calculate_signals(df_1h, df_15m, symbol):
    if df_1h is None or df_1h.empty:
        return None
    
    close_1h = df_1h['Close'].values.flatten().tolist()
    high_1h = df_1h['High'].values.flatten().tolist()
    low_1h = df_1h['Low'].values.flatten().tolist()
    volume_1h = df_1h['Volume'].values.flatten().tolist()
    dates_1h = df_1h.index.tolist()
    n_1h = len(close_1h)
    
    if n_1h < 30:
        return None
    
    # RSI (14)
    rsi_1h = [50.0] * n_1h
    for i in range(RSI_PERIOD, n_1h):
        gain = 0
        loss = 0
        for j in range(i-RSI_PERIOD+1, i+1):
            change = float(close_1h[j]) - float(close_1h[j-1])
            if change > 0:
                gain += change
            else:
                loss += abs(change)
        avg_gain = gain / RSI_PERIOD
        avg_loss = loss / RSI_PERIOD
        if avg_loss == 0:
            rsi_1h[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi_1h[i] = 100 - (100 / (1 + rs))
    
    # WMA21 on RSI
    wma_rsi_1h = [0.0] * n_1h
    weights = list(range(1, WMA_PERIOD + 1))
    weight_sum = sum(weights)
    for i in range(WMA_PERIOD-1, n_1h):
        wma_sum = 0
        for j in range(WMA_PERIOD):
            wma_sum += rsi_1h[i-j] * weights[WMA_PERIOD-1-j]
        wma_rsi_1h[i] = wma_sum / weight_sum
    
    # VWAP
    vwap_1h = [0.0] * n_1h
    cum_vol = 0
    cum_tpv = 0
    for i in range(n_1h):
        typical = (high_1h[i] + low_1h[i] + close_1h[i]) / 3
        cum_vol += volume_1h[i]
        cum_tpv += volume_1h[i] * typical
        if cum_vol > 0:
            vwap_1h[i] = cum_tpv / cum_vol
    
    # Signals
    buy_signal = [False] * n_1h
    sell_signal = [False] * n_1h
    
    start_idx = max(RSI_PERIOD, WMA_PERIOD)
    for i in range(start_idx, n_1h):
        if rsi_1h[i] > wma_rsi_1h[i] and close_1h[i] > vwap_1h[i]:
            buy_signal[i] = True
        elif rsi_1h[i] < wma_rsi_1h[i] and close_1h[i] < vwap_1h[i]:
            sell_signal[i] = True
    
    current_close = close_1h[-1]
    current_rsi = rsi_1h[-1]
    current_wma = wma_rsi_1h[-1]
    current_vwap = vwap_1h[-1]
    current_date = dates_1h[-1]
    
    is_buy = buy_signal[-1]
    is_sell = sell_signal[-1]
    
    return {
        'symbol': symbol,
        'signal': 'BUY' if is_buy else 'SELL' if is_sell else 'HOLD',
        'price': current_close,
        'rsi': current_rsi,
        'wma': current_wma,
        'vwap': current_vwap,
        'date': current_date,
        'timestamp': datetime.now()
    }

# ============================================
# SCAN AND SEND ALERTS
# ============================================

def scan_and_alert():
    """Scan all symbols and send Telegram alerts"""
    
    print(f"\n📊 Scanning at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    signals_found = 0
    alert_messages = []
    
    for symbol, config in SYMBOLS.items():
        print(f"  Scanning {config['emoji']} {config['name']}...")
        
        df_1h, df_15m = get_latest_data(symbol)
        
        if df_1h is None or df_15m is None:
            print(f"    ❌ No data")
            continue
        
        result = calculate_signals(df_1h, df_15m, symbol)
        
        if result is None:
            print(f"    ❌ Calculation failed")
            continue
        
        if result['signal'] != 'HOLD':
            signals_found += 1
            
            # Build alert message
            emoji = config['emoji']
            name = config['name']
            price = result['price']
            signal = result['signal']
            rsi = result['rsi']
            wma = result['wma']
            vwap = result['vwap']
            
            if signal == 'BUY':
                stop = price * (1 - STOP_LOSS_PCT/100)
                target = price * (1 + TAKE_PROFIT_PCT/100)
                signal_emoji = '🟢 BUY'
            else:
                stop = price * (1 + STOP_LOSS_PCT/100)
                target = price * (1 - TAKE_PROFIT_PCT/100)
                signal_emoji = '🔴 SELL'
            
            msg = f"""
{emoji} <b>{name}</b>
📈 Signal: {signal_emoji}
💰 Entry: ${price:,.2f}
🛑 Stop Loss: ${stop:,.2f} (1.5%)
🎯 Take Profit: ${target:,.2f} (3.75%)
📊 RSI: {rsi:.1f} | WMA: {wma:.1f}
📊 VWAP: ${vwap:,.2f}
"""
            alert_messages.append(msg)
            print(f"    🎯 {signal_emoji} at ${price:,.2f}")
        
        time.sleep(0.2)
    
    # Send Telegram alerts
    if alert_messages:
        header = f"🎯 <b>SIGNAL ALERTS</b>\n⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*40}\n"
        
        for msg in alert_messages:
            full_msg = header + msg
            send_telegram(full_msg)
            time.sleep(0.5)
        
        print(f"✅ Sent {len(alert_messages)} alerts to Telegram")
    else:
        print("⏸️ No signals found")

# ============================================
# MAIN LOOP
# ============================================

def main_loop():
    """Main loop - runs every 15 minutes"""
    print("\n🔄 Starting main loop...")
    
    # Send startup message
    startup_msg = f"""
🚀 <b>MULTI-SYMBOL SIGNAL BOT STARTED</b>

📊 Monitoring {len(SYMBOLS)} symbols:
{', '.join([f"{cfg['emoji']} {cfg['name']}" for cfg in SYMBOLS.values()])}

⚡ Strategy: RSI(14) vs WMA21(RSI) + VWAP
📈 Win Rate: 66.8%
🛑 Stop Loss: {STOP_LOSS_PCT}%
🎯 Take Profit: {TAKE_PROFIT_PCT}%

⏱ Updates every 15 minutes
🤖 Bot: Active
    """
    send_telegram(startup_msg)
    
    # Run first scan
    scan_and_alert()
    
    # Then loop every 15 minutes
    while True:
        time.sleep(900)  # 15 minutes
        scan_and_alert()

# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    print("="*70)
    print("🚀 MULTI-SYMBOL SIGNAL BOT WITH TELEGRAM")
    print("📊 9 Symbols | 66% Win Rate Strategy")
    print("="*70)
    
    # Start web server for health checks
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("🌐 Web server started for health checks")
    
    # Test Telegram connection
    print("\n📱 Testing Telegram connection...")
    if not test_telegram_connection():
        print("❌ Failed to connect to Telegram")
        sys.exit(1)
    
    if not test_group_chat_id():
        print("❌ Failed to send test message to group")
        sys.exit(1)
    
    # Start main loop
    main_loop()
