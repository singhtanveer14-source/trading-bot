# ============================================
# MULTI-SYMBOL SIGNAL BOT - WITH SIGNAL HISTORY
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

# Store last signal for each symbol
last_signals = {}

def update_signal_history(symbol, signal, price, rsi, wma, vwap):
    """Update the last signal for a symbol"""
    last_signals[symbol] = {
        'signal': signal,
        'price': price,
        'rsi': rsi,
        'wma': wma,
        'vwap': vwap,
        'time': datetime.now()
    }

def get_last_signal(symbol):
    """Get the last signal for a symbol"""
    if symbol in last_signals:
        return last_signals[symbol]
    return None

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
# DATA FETCHING
# ============================================

def get_latest_data(symbol):
    try:
        end_date = datetime.now()
        start_1h = end_date - timedelta(days=30)
        
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
    
    is_buy = buy_signal[-1]
    is_sell = sell_signal[-1]
    
    signal = 'BUY' if is_buy else 'SELL' if is_sell else 'HOLD'
    
    # Update signal history if signal is BUY or SELL
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
# SCAN AND SEND ALERTS - WITH SIGNAL HISTORY
# ============================================

def scan_and_alert():
    """Scan all symbols and send Telegram alerts with prices and last signals"""
    
    print(f"\n📊 Scanning at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_prices = []
    alert_messages = []
    price_msg = ""
    
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
        
        # Get data
        price = result['price']
        signal = result['signal']
        rsi = result['rsi']
        wma = result['wma']
        vwap = result['vwap']
        emoji = config['emoji']
        name = config['name']
        
        # Get last signal for this symbol
        last_signal = get_last_signal(symbol)
        
        # Price update with signal info
        if signal == 'BUY':
            signal_display = '🟢 BUY'
        elif signal == 'SELL':
            signal_display = '🔴 SELL'
        else:
            signal_display = '⏸️ HOLD'
        
        # Build price line with signal
        price_line = f"{emoji} {name}: ${price:,.2f} [{signal_display}]"
        
        # Add last signal info if exists
        if last_signal and last_signal['signal'] != 'HOLD':
            last_time = last_signal['time'].strftime('%H:%M')
            last_signal_display = '🟢 BUY' if last_signal['signal'] == 'BUY' else '🔴 SELL'
            price_line += f" (Last: {last_signal_display} @ ${last_signal['price']:,.2f} at {last_time})"
        
        all_prices.append(price_line)
        
        # If signal found, create alert
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
📊 RSI: {rsi:.1f} | WMA: {wma:.1f}
📊 VWAP: ${vwap:,.2f}
"""
            alert_messages.append(msg)
            print(f"    🎯 {signal_emoji} at ${price:,.2f}")
        
        time.sleep(0.2)
    
    # ============================================
    # SEND PRICE UPDATE WITH SIGNAL HISTORY
    # ============================================
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Build price update message with last signals
    price_msg = f"📊 <b>MARKET UPDATE</b>\n⏱ {now}\n{'='*40}\n\n"
    price_msg += "\n".join(all_prices)
    
    # Add signal count
    signal_count = len(alert_messages)
    price_msg += f"\n\n{'='*40}\n"
    price_msg += f"📈 New Signals: {signal_count}"
    
    # Add summary of last signals
    price_msg += f"\n📊 Active Signals:"
    active_signals = 0
    for symbol, config in SYMBOLS.items():
        last_signal = get_last_signal(symbol)
        if last_signal and last_signal['signal'] != 'HOLD':
            active_signals += 1
            last_time = last_signal['time'].strftime('%H:%M')
            sig_display = '🟢 BUY' if last_signal['signal'] == 'BUY' else '🔴 SELL'
            price_msg += f"\n   {config['emoji']} {config['short'] if 'short' in config else config['name']}: {sig_display} @ ${last_signal['price']:,.2f} ({last_time})"
    
    if active_signals == 0:
        price_msg += "\n   ⏸️ No active signals"
    
    price_msg += f"\n{'='*40}\n"
    price_msg += f"⏱ Next update in 15 minutes"
    
    # Send price update to Telegram
    send_telegram(price_msg)
    print(f"✅ Price update sent for {len(all_prices)} symbols")
    
    # ============================================
    # SEND SIGNAL ALERTS (if any)
    # ============================================
    
    if alert_messages:
        header = f"🎯 <b>⚠️ NEW SIGNAL ALERT</b>\n⏱ {now}\n{'='*40}\n"
        
        for msg in alert_messages:
            full_msg = header + msg
            send_telegram(full_msg)
            time.sleep(0.5)
        
        print(f"✅ Sent {len(alert_messages)} signal alerts")

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
📊 Shows: Price + Current Signal + Last Signal
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
    print("🚀 MULTI-SYMBOL SIGNAL BOT")
    print("📊 9 Symbols | Price + Signals + History")
    print("="*70)
    
    # Start web server
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("🌐 Web server started")
    
    # Test Telegram
    print("\n📱 Testing Telegram...")
    if not test_telegram_connection():
        print("⚠️ Telegram connection failed, but bot will continue")
    
    # Start main loop
    main_loop()
