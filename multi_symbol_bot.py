# multi_symbol_bot.py – 30‑minute cycle, thread starts on import
import os
import sys
import time
import threading
import requests
import numpy as np
from datetime import datetime, timedelta
import pytz
from flask import Flask
import yfinance as yf
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# ============================================
# TIMEZONE SETUP - INDIAN STANDARD TIME (IST)
# ============================================

IST = pytz.timezone('Asia/Kolkata')

def get_ist_time():
    return datetime.now(IST)

def get_ist_time_str():
    return get_ist_time().strftime('%Y-%m-%d %H:%M:%S')

def get_ist_time_short():
    return get_ist_time().strftime('%H:%M')

# ============================================
# TELEGRAM CREDENTIALS
# ============================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003971188413")

print("🚀 Starting Ultimate Trading Bot...")
print(f"Token: {'✅ Found' if TELEGRAM_TOKEN else '❌ Missing'}")
print(f"🕐 IST Time: {get_ist_time_str()}")

if not TELEGRAM_TOKEN:
    print("❌ No token! Exiting.")
    sys.exit(1)

# ============================================
# API KEYS & CONFIG
# ============================================

ALPHA_VANTAGE_API_KEY = "I9P5WDYIMQHADXV0"

RSI_PERIOD = 14
WMA_PERIOD = 21
STOP_LOSS_PCT = 1.5
TAKE_PROFIT_PCT = 3.75
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MIN = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MIN = 30
SCAN_INTERVAL_SECONDS = 1800  # 30 minutes

# ============================================
# FLASK APP
# ============================================

app = Flask(__name__)

@app.route('/')
def home():
    return f"✅ Ultimate Trading Bot is Running! (IST: {get_ist_time_str()})"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/status')
def status():
    """Check if the background thread is alive."""
    return {
        "status": "running",
        "thread_alive": bot_thread.is_alive() if 'bot_thread' in globals() else False,
        "ist_time": get_ist_time_str()
    }

@app.route('/scan')
def force_scan():
    print(f"🔍 Force scan triggered at {get_ist_time_str()}")
    def background_scan():
        try:
            scan_and_send()
        except Exception as e:
            print(f"❌ Scan error: {e}")
            send_telegram(f"⚠️ Scan error: {str(e)[:100]}")
    threading.Thread(target=background_scan).start()
    return f"✅ Scan started at {get_ist_time_str()}! Check Telegram."

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
            print(f"✅ Sent at {get_ist_time_short()}")
            return True
        print(f"❌ Failed: {response.status_code} – {response.text[:100]}")
        return False
    except Exception as e:
        print(f"❌ Error sending Telegram: {e}")
        return False

# ============================================
# PRICE CACHE & SIGNAL HISTORY (shortened)
# ============================================

price_cache = {}
cache_time = {}
signal_history = {}
signal_time = {}
trade_count = {}

def update_cache(symbol, price):
    price_cache[symbol] = price
    cache_time[symbol] = get_ist_time()

def get_cached_price(symbol):
    return price_cache.get(symbol)

def get_cache_time_str(symbol):
    if symbol in cache_time:
        return cache_time[symbol].strftime('%H:%M')
    return None

def update_signal(symbol, signal, price, rsi, wma, vwap, confidence=0):
    if symbol not in trade_count:
        trade_count[symbol] = 0
    if signal in ['BUY', 'SELL']:
        trade_count[symbol] += 1
    signal_history[symbol] = {
        'signal': signal,
        'price': price,
        'rsi': rsi,
        'wma': wma,
        'vwap': vwap,
        'confidence': confidence,
        'time': get_ist_time(),
        'trade_no': trade_count[symbol]
    }
    signal_time[symbol] = get_ist_time()

def get_last_signal(symbol):
    return signal_history.get(symbol)

# ============================================
# MARKET HOURS CHECK
# ============================================

def is_market_open():
    now = get_ist_time()
    if now.weekday() >= 5:
        return False
    current_minutes = now.hour * 60 + now.minute
    open_minutes = MARKET_OPEN_HOUR * 60 + MARKET_OPEN_MIN
    close_minutes = MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MIN
    return open_minutes <= current_minutes <= close_minutes

def get_market_status():
    return "🟢 OPEN" if is_market_open() else "🔴 CLOSED"

# ============================================
# DATA FETCHERS (same as before – abbreviated)
# ============================================

def get_binance(symbol):
    try:
        mapping = {'BTC': 'BTCUSDT', 'ETH': 'ETHUSDT', 'SOL': 'SOLUSDT'}
        if symbol not in mapping:
            return None
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={mapping[symbol]}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return float(response.json()['price'])
    except:
        pass
    return None

def get_coingecko(symbol):
    try:
        mapping = {'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana'}
        if symbol not in mapping:
            return None
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={mapping[symbol]}&vs_currencies=usd"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data[mapping[symbol]]['usd'])
    except:
        pass
    return None

def get_alpha_vantage(symbol):
    try:
        url = "https://www.alphavantage.co/query"
        params = {'function': 'GLOBAL_QUOTE', 'symbol': symbol, 'apikey': ALPHA_VANTAGE_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'Global Quote' in data and '05. price' in data['Global Quote']:
                return float(data['Global Quote']['05. price'])
    except:
        pass
    return None

def get_gold_price():
    try:
        price = get_alpha_vantage('XAUUSD')
        if price:
            update_cache('GOLD', price)
            return price
    except:
        pass
    try:
        url = "https://api.gold-api.com/price/XAU"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'price' in data:
                price = float(data['price'])
                update_cache('GOLD', price)
                return price
    except:
        pass
    return get_cached_price('GOLD')

def get_silver_price():
    try:
        price = get_alpha_vantage('XAGUSD')
        if price:
            update_cache('SILVER', price)
            return price
    except:
        pass
    try:
        url = "https://api.gold-api.com/price/XAG"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'price' in data:
                price = float(data['price'])
                update_cache('SILVER', price)
                return price
    except:
        pass
    return get_cached_price('SILVER')

def get_yfinance_price(symbol, cache_key):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            price = float(data['Close'].iloc[-1])
            update_cache(cache_key, price)
            return price
        data = ticker.history(period="5d", interval="1h")
        if not data.empty:
            price = float(data['Close'].iloc[-1])
            update_cache(cache_key, price)
            return price
        return get_cached_price(cache_key)
    except:
        return get_cached_price(cache_key)

def get_nifty_price():
    return get_yfinance_price('^NSEI', 'NIFTY')

def get_banknifty_price():
    return get_yfinance_price('^NSEBANK', 'BANKNIFTY')

def get_sensex_price():
    return get_yfinance_price('^BSESN', 'SENSEX')

# ============================================
# TRADING LOGIC
# ============================================

def calculate_rsi(data, period=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_wma(data, period=21):
    weights = np.arange(1, period + 1)
    def wma_func(x):
        return np.sum(x * weights) / weights.sum()
    return data.rolling(period).apply(wma_func, raw=True)

def calculate_vwap(df):
    typical = (df['High'] + df['Low'] + df['Close']) / 3
    cum_vol = df['Volume'].cumsum()
    cum_tpv = (typical * df['Volume']).cumsum()
    vwap = cum_tpv / cum_vol
    return vwap

def get_historical_data(symbol, period='7d', interval='1h'):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except:
        return None

def calculate_confidence(rsi, wma, price, vwap):
    confidence = 50
    rsi_diff = rsi - wma
    if abs(rsi_diff) > 20:
        confidence += 20
    elif abs(rsi_diff) > 10:
        confidence += 15
    elif abs(rsi_diff) > 5:
        confidence += 10
    vwap_diff = (price - vwap) / vwap * 100
    if abs(vwap_diff) > 2:
        confidence += 20
    elif abs(vwap_diff) > 1:
        confidence += 15
    elif abs(vwap_diff) > 0.5:
        confidence += 10
    if (rsi > wma and price > vwap) or (rsi < wma and price < vwap):
        confidence += 10
    return min(100, max(0, confidence))

def generate_signal(symbol, price):
    try:
        ticker_map = {
            'BTC': 'BTC-USD',
            'ETH': 'ETH-USD',
            'SOL': 'SOL-USD',
            'GOLD': 'GC=F',
            'SILVER': 'SI=F',
            'NIFTY': '^NSEI',
            'BANKNIFTY': '^NSEBANK',
            'SENSEX': '^BSESN'
        }
        df = get_historical_data(ticker_map.get(symbol, symbol))
        if df is None or df.empty or len(df) < 30:
            return None
        df['RSI'] = calculate_rsi(df['Close'], RSI_PERIOD)
        df['WMA'] = calculate_wma(df['RSI'], WMA_PERIOD)
        df['VWAP'] = calculate_vwap(df)
        last = df.iloc[-1]
        rsi = last['RSI']
        wma = last['WMA']
        vwap = last['VWAP']
        if rsi > wma and price > vwap:
            signal = 'BUY'
        elif rsi < wma and price < vwap:
            signal = 'SELL'
        else:
            signal = 'HOLD'
        confidence = calculate_confidence(rsi, wma, price, vwap)
        if signal in ['BUY', 'SELL']:
            update_signal(symbol, signal, price, rsi, wma, vwap, confidence)
        return {
            'signal': signal,
            'price': price,
            'rsi': rsi,
            'wma': wma,
            'vwap': vwap,
            'confidence': confidence
        }
    except Exception as e:
        print(f"Signal error for {symbol}: {e}")
        return None

# ============================================
# SYMBOLS
# ============================================

SYMBOLS = [
    {'key': 'BTC', 'name': 'Bitcoin', 'emoji': '🟢', 'fetcher': lambda: get_binance('BTC') or get_coingecko('BTC')},
    {'key': 'ETH', 'name': 'Ethereum', 'emoji': '🟣', 'fetcher': lambda: get_binance('ETH') or get_coingecko('ETH')},
    {'key': 'SOL', 'name': 'Solana', 'emoji': '🟠', 'fetcher': lambda: get_binance('SOL') or get_coingecko('SOL')},
    {'key': 'GOLD', 'name': 'Gold', 'emoji': '🥇', 'fetcher': get_gold_price},
    {'key': 'SILVER', 'name': 'Silver', 'emoji': '🥈', 'fetcher': get_silver_price},
    {'key': 'NIFTY', 'name': 'NIFTY 50', 'emoji': '🇮🇳', 'fetcher': get_nifty_price},
    {'key': 'BANKNIFTY', 'name': 'BANKNIFTY', 'emoji': '🏦', 'fetcher': get_banknifty_price},
    {'key': 'SENSEX', 'name': 'SENSEX', 'emoji': '📊', 'fetcher': get_sensex_price}
]

# ============================================
# SCAN AND SEND
# ============================================

def scan_and_send():
    ist_now = get_ist_time()
    print(f"\n📊 Scanning at {ist_now.strftime('%H:%M:%S')} IST")
    try:
        today = ist_now.strftime('%A')
        market_status = get_market_status()
        prices = []
        signals_list = []
        failed = []
        success_count = 0
        signal_count = 0
        for info in SYMBOLS:
            try:
                print(f"  Fetching {info['name']}...")
                price = info['fetcher']()
                if price and price > 0:
                    success_count += 1
                    signal_data = generate_signal(info['key'], price)
                    if info['key'] in ['NIFTY', 'BANKNIFTY', 'SENSEX']:
                        price_str = f"{info['emoji']} {info['name']}: {price:,.2f}"
                    else:
                        price_str = f"{info['emoji']} {info['name']}: ${price:,.2f}"
                    if signal_data and signal_data['signal'] != 'HOLD':
                        signal_display = '🟢 BUY' if signal_data['signal'] == 'BUY' else '🔴 SELL'
                        conf = signal_data.get('confidence', 50)
                        price_str += f" [{signal_display} {conf:.0f}%]"
                        signal_count += 1
                        signals_list.append(
                            f"{info['emoji']} {info['name']}: {signal_display} at ${price:,.2f} "
                            f"(Confidence: {conf:.0f}%)"
                        )
                    last_signal = get_last_signal(info['key'])
                    if last_signal:
                        last_time = last_signal['time'].strftime('%H:%M')
                        last_display = '🟢 BUY' if last_signal['signal'] == 'BUY' else '🔴 SELL'
                        trade_no = last_signal.get('trade_no', 0)
                        price_str += f" (Last: {last_display} @ ${last_signal['price']:,.2f} at {last_time} | T#{trade_no})"
                    cache_time_str = get_cache_time_str(info['key'])
                    if cache_time_str:
                        price_str += f" 📊 (Updated: {cache_time_str} IST)"
                    prices.append(price_str)
                    print(f"    ✅ {price:,.2f}")
                else:
                    failed.append(info['name'])
                    print(f"    ❌ No data")
            except Exception as e:
                failed.append(info['name'])
                print(f"    ❌ Error: {e}")
            time.sleep(12)

        now = ist_now.strftime('%Y-%m-%d %H:%M:%S')
        msg = f"📊 <b>MARKET UPDATE</b>\n⏱ {now} <b>IST</b>\n📅 {today} | {market_status}\n" + "="*45 + "\n\n"
        if prices:
            msg += "\n".join(prices)
            msg += f"\n\n✅ Updated: {success_count}/{len(SYMBOLS)} symbols"
        else:
            msg += "⚠️ No prices available"
        if signals_list:
            msg += f"\n\n📈 <b>ACTIVE SIGNALS: {len(signals_list)}</b>\n"
            msg += "\n".join(signals_list)
        total_trades = sum(trade_count.values())
        if total_trades > 0:
            msg += f"\n\n📊 <b>TRADE STATISTICS</b>\n"
            msg += f"   Total Trades: {total_trades}\n"
            for key, count in trade_count.items():
                if count > 0:
                    symbol_name = next((s['name'] for s in SYMBOLS if s['key'] == key), key)
                    msg += f"   {symbol_name}: {count}\n"
        if failed:
            msg += f"\n\n❌ Failed: {', '.join(failed)}"
        next_update = ist_now + timedelta(seconds=SCAN_INTERVAL_SECONDS)
        msg += f"\n\n⏱ Next update at {next_update.strftime('%H:%M')} IST"
        send_telegram(msg)
    except Exception as e:
        print(f"❌ scan_and_send error: {e}")
        send_telegram(f"⚠️ Scan error: {str(e)[:100]}")

# ============================================
# MAIN LOOP (30-min cycle)
# ============================================

def main_loop():
    print("\n🔄 Starting main loop (30-minute cycle)...")
    ist_now = get_ist_time()
    send_telegram(f"""
🚀 <b>ULTIMATE TRADING BOT</b>
🕐 <b>IST</b>: {ist_now.strftime('%Y-%m-%d %H:%M:%S')}
📊 8 Symbols | RSI(14) + WMA21 + VWAP
⏱ Updates every 30 minutes
""")
    time.sleep(2)
    scan_and_send()
    loop_count = 0
    while True:
        try:
            loop_count += 1
            print(f"\n🔄 Loop #{loop_count} at {get_ist_time_str()}")
            for minute in range(SCAN_INTERVAL_SECONDS // 60):
                time.sleep(60)
                if (loop_count % 4 == 0) and (minute == 0):
                    send_telegram(f"💓 Bot heartbeat – {get_ist_time_str()} IST")
            scan_and_send()
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            send_telegram(f"⚠️ Bot error: {str(e)[:100]}")
            time.sleep(60)

# ============================================
# START THE BACKGROUND THREAD – ON IMPORT
# ============================================

print("🚀 Starting background thread...")
bot_thread = threading.Thread(target=main_loop, daemon=True)
bot_thread.start()
print(f"✅ Background thread started (alive={bot_thread.is_alive()})")

# ============================================
# FLASK WEB SERVER
# ============================================

if __name__ == "__main__":
    print("="*50)
    print("🚀 ULTIMATE TRADING BOT - IST (30-min cycle)")
    print(f"🕐 Current IST: {get_ist_time_str()}")
    print("="*50)
    run_web_server()
