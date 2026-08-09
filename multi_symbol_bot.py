# ============================================
# MULTI-SYMBOL SIGNAL BOT - FORCED STARTUP FIX
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
# TELEGRAM CREDENTIALS
# ============================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003971188413")

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
    return "🚀 Multi-Symbol Signal Bot is Running!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/test-telegram')
def test_telegram():
    print("🧪 Test endpoint called!")
    result = send_telegram("🧪 Test message from multi-symbol bot! Bot is active!")
    if result:
        return "✅ Test message sent to Telegram! Check your group!"
    else:
        return "❌ Failed to send test message. Check logs.", 500

@app.route('/force-scan')
def force_scan():
    """Force an immediate scan"""
    print("🔍 Force scan triggered!")
    scan_and_alert()
    return "✅ Scan completed! Check Telegram for updates."

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
# SIGNAL HISTORY TRACKING
# ============================================

last_signals = {}

def update_signal_history(symbol, signal, price, rsi, wma, vwap):
    last_signals[symbol] = {
        'signal': signal,
        'price': price,
        'rsi': rsi,
        'wma': wma,
        'vwap': vwap,
        'time': datetime.now()
    }

def get_last_signal(symbol):
    if symbol in last_signals:
        return last_signals[symbol]
    return None

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
        print("📤 Sending Telegram...")
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
# DATA FETCHING
# ============================================

def get_latest_data(symbol):
    try:
        end_date = datetime.now()
        start_1h = end_date - timedelta(days=7)  # Reduced to 7 days for faster loading
        
        df_1h = yf.download(symbol, start=start_1h, end=end_date, 
                            interval='1h', progress=False)
        
        if df_1h.empty:
            return None, None
        
        if hasattr(df_1h, 'columns') and isinstance(df_1h.columns, pd.MultiIndex):
            df_1h.columns = df_1h.columns.get_level_values(0)
        
        return df_1h, None
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
    n_1h = len(close_1h)
    
    if n_1h < 10:
        return None
    
    # RSI (14)
    rsi_1h = [50.0] * n_1h
    for i in range(min(RSI_PERIOD, n_1h-1), n_1h):
        gain = 0
        loss = 0
        for j in range(max(0, i-RSI_PERIOD+1), i+1):
            change = float(close_1h[j]) - float(close_1h[j-1])
            if change > 0:
                gain += change
            else:
                loss += abs(change)
        if i >= RSI_PERIOD:
            avg_gain = gain / RSI_PERIOD
            avg_loss = loss / RSI_PERIOD
            if avg_loss == 0:
                rsi_1h[i] = 100
            else:
                rs = avg_gain / avg_loss
                rsi_1h[i] = 100 - (100 / (1 + rs))
    
    # WMA21 on RSI
    wma_rsi_1h = [0.0] * n_1h
    weights = list(range(1, min(WMA_PERIOD, 22)))
    weight_sum = sum(weights)
    for i in range(min(WMA_PERIOD-1, n_1h-1), n_1h):
        if i >= WMA_PERIOD-1:
            wma_sum = 0
            for j in range(WMA_PERIOD):
                wma_sum += rsi_1h[i-j] * weights[WMA_PERIOD-1-j]
            wma_rsi_1h[i] = wma_sum / weight_sum
    
    # VWAP (simplified)
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
    for i in range(min(start_idx, n_1h-1), n_1h):
        if rsi_1h[i] > wma_rsi_1h[i] and close_1h[i] > vwap_1h[i]:
            buy_signal[i] = True
        elif rsi_1h[i] < wma_rsi_1h[i] and close_1h[i] < vwap_1h[i]:
            sell_signal[i] = True
    
    current_close = close_1h[-1]
    current_rsi = rsi_1h[-1]
    current_wma = wma_rsi_1h[-1]
    current_vwap = vwap_1h[-1]
    
    is_buy = buy_signal[-1]
    is_sell = sell_signal[-1]
    
    signal = 'BUY' if is_buy else 'SELL' if is_sell else 'HOLD'
    
    if signal in ['BUY', 'SELL']:
        update_signal_history(symbol, signal, current_close, current_rsi, current_wma, current_vwap)
    
    return {
        'symbol': symbol,
        'signal': signal,
        'price': current_close,
        'rsi': current_rsi,
        'wma': current_wma,
        'vwap': current_vwap,
        'timestamp': datetime.now()
    }

# ============================================
# SCAN AND SEND ALERTS
# ============================================

def scan_and_alert():
    """Scan all symbols and send Telegram alerts"""
    
    print(f"\n📊 Scanning at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_prices = []
    alert_messages = []
    
    for symbol, config in SYMBOLS.items():
        print(f"  Scanning {config['emoji']} {config['name']}...")
        
        df_1h, df_15m = get_latest_data(symbol)
        
        if df_1h is None:
            print(f"    ❌ No data")
            continue
        
        result = calculate_signals(df_1h, df_15m, symbol)
        
        if result is None:
            print(f"    ❌ Calculation failed")
            continue
        
        price = result['price']
        signal = result['signal']
        emoji = config['emoji']
        name = config['name']
        
        # Price line
        if signal == 'BUY':
            signal_display = '🟢 BUY'
        elif signal == 'SELL':
            signal_display = '🔴 SELL'
        else:
            signal_display = '⏸️ HOLD'
        
        price_line = f"{emoji} {name}: ${price:,.2f} [{signal_display}]"
        
        # Add last signal
        last_signal = get_last_signal(symbol)
        if last_signal and last_signal['signal'] != 'HOLD':
            last_time = last_signal['time'].strftime('%H:%M')
            last_signal_display = '🟢 BUY' if last_signal['signal'] == 'BUY' else '🔴 SELL'
            price_line += f" (Last: {last_signal_display} @ ${last_signal['price']:,.2f} at {last_time})"
        
        all_prices.append(price_line)
        
        # Signal alert
        if signal != 'HOLD':
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
"""
            alert_messages.append(msg)
            print(f"    🎯 {signal_emoji} at ${price:,.2f}")
        
        time.sleep(0.2)
    
    # Send price update
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    price_msg = f"📊 <b>MARKET UPDATE</b>\n⏱ {now}\n{'='*40}\n\n"
    price_msg += "\n".join(all_prices)
    price_msg += f"\n\n{'='*40}\n"
    price_msg += f"📈 New Signals: {len(alert_messages)}"
    price_msg += f"\n⏱ Next update in 15 minutes"
    
    send_telegram(price_msg)
    print(f"✅ Price update sent")
    
    # Send signal alerts
    if alert_messages:
        header = f"🎯 <b>⚠️ NEW SIGNAL ALERT</b>\n⏱ {now}\n{'='*40}\n"
        for msg in alert_messages:
            send_telegram(header + msg)
            time.sleep(0.5)

# ============================================
# MAIN LOOP
# ============================================

def main_loop():
    """Main loop - runs every 15 minutes"""
    print("\n🔄 Starting main loop...")
    print("📤 Sending startup message...")
    
    # Send startup message
    startup_msg = f"""
🚀 <b>MULTI-SYMBOL SIGNAL BOT STARTED</b>

📊 Monitoring {len(SYMBOLS)} symbols
⚡ Strategy: RSI(14) vs WMA21(RSI) + VWAP
📈 Win Rate: 66.8%
🛑 Stop Loss: {STOP_LOSS_PCT}%
🎯 Take Profit: {TAKE_PROFIT_PCT}%

⏱ Updates every 15 minutes
🤖 Bot: Active
    """
    send_telegram(startup_msg)
    
    # Run first scan
    print("📊 Running first scan...")
    scan_and_alert()
    
    # Then loop
    print("🔄 Entering 15-minute loop...")
    while True:
        time.sleep(900)
        scan_and_alert()

# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    print("="*70)
    print("🚀 MULTI-SYMBOL SIGNAL BOT")
    print("="*70)
    
    # Start web server
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("🌐 Web server started")
    
    # Start main loop
    print("🚀 Starting main loop...")
    main_loop()
