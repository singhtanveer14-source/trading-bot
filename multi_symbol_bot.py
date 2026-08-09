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

print("🚀 Starting Trading Bot...")
print(f"Token: {'✅ Found' if TELEGRAM_TOKEN else '❌ Missing'}")
print(f"Chat ID: {TELEGRAM_CHAT_ID}")

if not TELEGRAM_TOKEN:
    print("❌ No token!")
    sys.exit(1)

# ============================================
# FLASK APP
# ============================================

app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 Trading Bot is Running!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/send')
def send_test():
    result = send_telegram("🧪 Bot is working!")
    return "✅ Sent!" if result else "❌ Failed", 500

@app.route('/scan')
def force_scan():
    print("🔍 Force scan triggered!")
    scan_and_send(force=True)
    return "✅ Scan completed! Check Telegram."

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ============================================
# TELEGRAM
# ============================================

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Sent")
            return True
        print(f"❌ Failed: {response.status_code}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# ============================================
# STRATEGY PARAMETERS
# ============================================

RSI_PERIOD = 14
WMA_PERIOD = 21
STOP_LOSS_PCT = 1.5
TAKE_PROFIT_PCT = 3.75

# ============================================
# SYMBOLS
# ============================================

SYMBOLS = {
    'BTC-USD': {'name': 'Bitcoin', 'emoji': '🟢'},
    'ETH-USD': {'name': 'Ethereum', 'emoji': '🟣'},
    'SOL-USD': {'name': 'Solana', 'emoji': '🟠'},
    'GC=F': {'name': 'Gold', 'emoji': '🥇'},
    'SI=F': {'name': 'Silver', 'emoji': '🥈'},
    'CL=F': {'name': 'Crude Oil', 'emoji': '🛢️'},
    '^NSEI': {'name': 'NIFTY 50', 'emoji': '🇮🇳'},
    '^NSEBANK': {'name': 'BANKNIFTY', 'emoji': '🏦'},
    '^BSESN': {'name': 'SENSEX', 'emoji': '📊'}
}

# ============================================
# SIGNAL HISTORY
# ============================================

last_signals = {}

def update_signal(symbol, signal, price, rsi, wma, vwap):
    last_signals[symbol] = {
        'signal': signal,
        'price': price,
        'rsi': rsi,
        'wma': wma,
        'vwap': vwap,
        'time': datetime.now()
    }

def get_last_signal(symbol):
    return last_signals.get(symbol)

# ============================================
# STRATEGY CALCULATIONS
# ============================================

def calculate_strategy(df, symbol):
    """Calculate RSI, WMA, VWAP and generate signal"""
    
    if df is None or df.empty or len(df) < 30:
        return None
    
    close = df['Close'].values
    high = df['High'].values
    low = df['Low'].values
    volume = df['Volume'].values
    n = len(close)
    
    # RSI
    rsi = [50.0] * n
    for i in range(min(RSI_PERIOD, n), n):
        gain = 0
        loss = 0
        for j in range(max(0, i-RSI_PERIOD+1), i+1):
            change = close[j] - close[j-1]
            if change > 0:
                gain += change
            else:
                loss += abs(change)
        avg_gain = gain / RSI_PERIOD
        avg_loss = loss / RSI_PERIOD
        if avg_loss == 0:
            rsi[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))
    
    # WMA on RSI
    wma_rsi = [0.0] * n
    weights = list(range(1, min(WMA_PERIOD, 22)))
    weight_sum = sum(weights)
    for i in range(min(WMA_PERIOD-1, n-1), n):
        if i >= WMA_PERIOD-1:
            wma_sum = 0
            for j in range(WMA_PERIOD):
                wma_sum += rsi[i-j] * weights[WMA_PERIOD-1-j]
            wma_rsi[i] = wma_sum / weight_sum
    
    # VWAP
    vwap = [0.0] * n
    cum_vol = 0
    cum_tpv = 0
    for i in range(n):
        typical = (high[i] + low[i] + close[i]) / 3
        cum_vol += volume[i]
        cum_tpv += volume[i] * typical
        if cum_vol > 0:
            vwap[i] = cum_tpv / cum_vol
    
    current_idx = n - 1
    current_close = close[current_idx]
    current_rsi = rsi[current_idx]
    current_wma = wma_rsi[current_idx]
    current_vwap = vwap[current_idx]
    
    # STRATEGY LOGIC
    signal = 'HOLD'
    
    # BUY: RSI > WMA AND Price > VWAP
    if current_rsi > current_wma and current_close > current_vwap:
        signal = 'BUY'
    # SELL: RSI < WMA AND Price < VWAP
    elif current_rsi < current_wma and current_close < current_vwap:
        signal = 'SELL'
    
    # Update history if signal
    if signal in ['BUY', 'SELL']:
        update_signal(symbol, signal, current_close, current_rsi, current_wma, current_vwap)
    
    return {
        'price': current_close,
        'rsi': current_rsi,
        'wma': current_wma,
        'vwap': current_vwap,
        'signal': signal,
        'timestamp': datetime.now()
    }

# ============================================
# FETCH DATA
# ============================================

def fetch_data(symbol):
    """Fetch data for strategy"""
    try:
        # Try 1h data
        df = yf.download(symbol, period='3d', interval='1h', progress=False)
        if not df.empty and len(df) >= 30:
            return df
        
        # Fallback to 15m
        df = yf.download(symbol, period='2d', interval='15m', progress=False)
        if not df.empty and len(df) >= 30:
            return df
        
        # Fallback to 1d
        df = yf.download(symbol, period='30d', interval='1d', progress=False)
        if not df.empty and len(df) >= 30:
            return df
        
        return None
    except Exception as e:
        print(f"  Error fetching {symbol}: {e}")
        return None

# ============================================
# SCAN AND SEND
# ============================================

def scan_and_send(force=False):
    print(f"\n📊 Scanning at {datetime.now().strftime('%H:%M:%S')}")
    
    prices = []
    signals = []
    errors = []
    
    for symbol, info in SYMBOLS.items():
        try:
            print(f"  Fetching {info['name']}...")
            df = fetch_data(symbol)
            
            if df is None:
                errors.append(f"❌ {info['name']}: No data")
                continue
            
            result = calculate_strategy(df, symbol)
            
            if result is None:
                errors.append(f"❌ {info['name']}: Calculation failed")
                continue
            
            price = result['price']
            signal = result['signal']
            emoji = info['emoji']
            name = info['name']
            
            # Price line with signal
            signal_display = '🟢 BUY' if signal == 'BUY' else '🔴 SELL' if signal == 'SELL' else '⏸️ HOLD'
            price_line = f"{emoji} {name}: ${price:,.2f} [{signal_display}]"
            
            # Add last signal
            last = get_last_signal(symbol)
            if last and last['signal'] != 'HOLD':
                last_time = last['time'].strftime('%H:%M')
                last_signal = '🟢 BUY' if last['signal'] == 'BUY' else '🔴 SELL'
                price_line += f" (Last: {last_signal} @ ${last['price']:,.2f} at {last_time})"
            
            prices.append(price_line)
            
            # Signal alert
            if signal != 'HOLD':
                stop = price * (1 - STOP_LOSS_PCT/100)
                target = price * (1 + TAKE_PROFIT_PCT/100)
                signal_emoji = '🟢 BUY' if signal == 'BUY' else '🔴 SELL'
                
                signals.append(f"""
{emoji} <b>{name}</b>
📈 Signal: {signal_emoji}
💰 Entry: ${price:,.2f}
🛑 Stop Loss: ${stop:,.2f} (1.5%)
🎯 Take Profit: ${target:,.2f} (3.75%)
📊 RSI: {result['rsi']:.1f} | WMA: {result['wma']:.1f}
📊 VWAP: ${result['vwap']:,.2f}
""")
            
        except Exception as e:
            errors.append(f"❌ {info['name']}: {str(e)[:30]}")
            print(f"  ❌ {e}")
        
        time.sleep(0.3)
    
    # Build message
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # PRICE UPDATE
    price_msg = f"📊 <b>MARKET UPDATE</b>\n⏱ {now}\n{'='*40}\n\n"
    price_msg += "\n".join(prices) if prices else "⚠️ No prices"
    price_msg += f"\n\n✅ Updated: {len(prices)}/{len(SYMBOLS)} symbols"
    price_msg += f"\n📈 New Signals: {len(signals)}"
    price_msg += "\n⏱ Next update in 15 minutes"
    
    send_telegram(price_msg)
    
    # SIGNAL ALERTS
    if signals:
        for signal_msg in signals:
            send_telegram("🎯 <b>⚠️ SIGNAL ALERT</b>\n" + signal_msg)
            time.sleep(0.5)

# ============================================
# MAIN LOOP
# ============================================

def main_loop():
    print("\n🔄 Starting main loop...")
    
    send_telegram("""
🚀 <b>TRADING BOT STARTED</b>

📊 Monitoring 9 symbols
⚡ Strategy: RSI(14) vs WMA21(RSI) + VWAP
🛑 Stop Loss: 1.5%
🎯 Take Profit: 3.75%

⏱ Updates every 15 minutes
    """)
    
    time.sleep(2)
    scan_and_send()
    
    loop_count = 0
    while True:
        time.sleep(900)
        loop_count += 1
        print(f"\n🔄 Loop #{loop_count}")
        scan_and_send()

# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    print("="*50)
    print("🚀 TRADING BOT")
    print("="*50)
    
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("🌐 Web server started")
    
    main_loop()
