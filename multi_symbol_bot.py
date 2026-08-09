import os
import sys
import time
import threading
import requests
from datetime import datetime, timedelta
from flask import Flask
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

# ============================================
# TELEGRAM CREDENTIALS
# ============================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003971188413")

print("🚀 Starting Hybrid Trading Bot...")
print(f"Token: {'✅ Found' if TELEGRAM_TOKEN else '❌ Missing'}")

if not TELEGRAM_TOKEN:
    print("❌ No token!")
    sys.exit(1)

# ============================================
# ALPHA VANTAGE API KEY
# ============================================

ALPHA_VANTAGE_API_KEY = "I9P5WDYIMQHADXV0"

# ============================================
# FLASK APP
# ============================================

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Hybrid Trading Bot is Running!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/scan')
def force_scan():
    print("🔍 Force scan triggered!")
    def background_scan():
        try:
            scan_and_send()
        except Exception as e:
            print(f"❌ Scan error: {e}")
            send_telegram(f"⚠️ Scan error: {str(e)[:100]}")
    threading.Thread(target=background_scan).start()
    return "✅ Scan started! Check Telegram in 2-3 minutes."

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
# PRICE CACHE
# ============================================

price_cache = {}
cache_time = {}

def update_cache(symbol, price):
    price_cache[symbol] = price
    cache_time[symbol] = datetime.now()

def get_cached_price(symbol):
    return price_cache.get(symbol)

def get_cache_time_str(symbol):
    if symbol in cache_time:
        return cache_time[symbol].strftime('%H:%M')
    return None

# ============================================
# CRYPTO - BINANCE + COINGECKO
# ============================================

def get_binance(symbol):
    try:
        mapping = {
            'BTC': 'BTCUSDT',
            'ETH': 'ETHUSDT',
            'SOL': 'SOLUSDT'
        }
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
        mapping = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'SOL': 'solana'
        }
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

# ============================================
# GOLD - MULTIPLE SOURCES
# ============================================

def get_gold_price():
    """Gold from multiple sources"""
    
    # 1. Alpha Vantage
    try:
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': 'XAUUSD',
            'apikey': ALPHA_VANTAGE_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'Global Quote' in data and '05. price' in data['Global Quote']:
                price = float(data['Global Quote']['05. price'])
                update_cache('GOLD', price)
                return price
    except:
        pass
    
    # 2. Gold-API
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
    
    # 3. Yahoo Finance (backup)
    try:
        ticker = yf.Ticker('GC=F')
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            price = float(data['Close'].iloc[-1])
            update_cache('GOLD', price)
            return price
    except:
        pass
    
    return get_cached_price('GOLD')

# ============================================
# SILVER - MULTIPLE SOURCES
# ============================================

def get_silver_price():
    """Silver from multiple sources"""
    
    # 1. Alpha Vantage
    try:
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': 'XAGUSD',
            'apikey': ALPHA_VANTAGE_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'Global Quote' in data and '05. price' in data['Global Quote']:
                price = float(data['Global Quote']['05. price'])
                update_cache('SILVER', price)
                return price
    except:
        pass
    
    # 2. Gold-API
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
    
    # 3. Yahoo Finance (backup)
    try:
        ticker = yf.Ticker('SI=F')
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            price = float(data['Close'].iloc[-1])
            update_cache('SILVER', price)
            return price
    except:
        pass
    
    return get_cached_price('SILVER')

# ============================================
# CRUDE OIL - MULTIPLE SOURCES
# ============================================

def get_oil_price():
    """Crude Oil from multiple sources"""
    
    # 1. Alpha Vantage
    try:
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': 'CL',
            'apikey': ALPHA_VANTAGE_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'Global Quote' in data and '05. price' in data['Global Quote']:
                price = float(data['Global Quote']['05. price'])
                update_cache('OIL', price)
                return price
    except:
        pass
    
    # 2. Yahoo Finance
    try:
        ticker = yf.Ticker('CL=F')
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            price = float(data['Close'].iloc[-1])
            update_cache('OIL', price)
            return price
    except:
        pass
    
    # 3. Alpha Vantage with WTI
    try:
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': 'WTI',
            'apikey': ALPHA_VANTAGE_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'Global Quote' in data and '05. price' in data['Global Quote']:
                price = float(data['Global Quote']['05. price'])
                update_cache('OIL', price)
                return price
    except:
        pass
    
    return get_cached_price('OIL')

# ============================================
# INDIAN INDICES - YAHOO FINANCE
# ============================================

def get_yfinance_price(symbol, cache_key):
    """Get price from Yahoo Finance"""
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
# SYMBOLS
# ============================================

SYMBOLS = [
    {'key': 'BTC', 'name': 'Bitcoin', 'emoji': '🟢', 'fetcher': lambda: get_binance('BTC') or get_coingecko('BTC')},
    {'key': 'ETH', 'name': 'Ethereum', 'emoji': '🟣', 'fetcher': lambda: get_binance('ETH') or get_coingecko('ETH')},
    {'key': 'SOL', 'name': 'Solana', 'emoji': '🟠', 'fetcher': lambda: get_binance('SOL') or get_coingecko('SOL')},
    {'key': 'GOLD', 'name': 'Gold', 'emoji': '🥇', 'fetcher': get_gold_price},
    {'key': 'SILVER', 'name': 'Silver', 'emoji': '🥈', 'fetcher': get_silver_price},
    {'key': 'OIL', 'name': 'Crude Oil', 'emoji': '🛢️', 'fetcher': get_oil_price},
    {'key': 'NIFTY', 'name': 'NIFTY 50', 'emoji': '🇮🇳', 'fetcher': get_nifty_price},
    {'key': 'BANKNIFTY', 'name': 'BANKNIFTY', 'emoji': '🏦', 'fetcher': get_banknifty_price},
    {'key': 'SENSEX', 'name': 'SENSEX', 'emoji': '📊', 'fetcher': get_sensex_price}
]

# ============================================
# SCAN
# ============================================

def scan_and_send():
    print(f"\n📊 Scanning at {datetime.now().strftime('%H:%M:%S')}")
    
    today = datetime.now().strftime('%A')
    is_weekend = datetime.now().weekday() >= 5
    weekday_status = "🟢 Markets Open" if not is_weekend else "🔴 Markets Closed (Weekend)"
    
    prices = []
    failed = []
    cached_list = []
    success_count = 0
    
    send_telegram(f"🔄 Market Data | {today}")
    
    for info in SYMBOLS:
        try:
            print(f"  Fetching {info['name']}...")
            price = info['fetcher']()
            
            if price and price > 0:
                success_count += 1
                
                # Format price
                if info['key'] in ['NIFTY', 'BANKNIFTY', 'SENSEX']:
                    price_str = f"{info['emoji']} {info['name']}: {price:,.2f}"
                else:
                    price_str = f"{info['emoji']} {info['name']}: ${price:,.2f}"
                
                # Check if cached
                cache_time_str = get_cache_time_str(info['key'])
                if cache_time_str:
                    price_str += f" 📊 (Last: {cache_time_str})"
                    cached_list.append(info['name'])
                
                prices.append(price_str)
                print(f"    ✅ {price:,.2f}")
            else:
                failed.append(info['name'])
                print(f"    ❌ No data")
        except Exception as e:
            failed.append(info['name'])
            print(f"    ❌ Error: {e}")
        
        time.sleep(12)
    
    # Build message
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    msg = f"📊 <b>MARKET UPDATE</b>\n"
    msg += f"⏱ {now}\n"
    msg += f"📅 {today}\n"
    msg += "="*40 + "\n\n"
    
    if prices:
        msg += "\n".join(prices)
        msg += f"\n\n✅ Updated: {success_count}/{len(SYMBOLS)} symbols"
    else:
        msg += "⚠️ No prices available"
    
    if failed:
        msg += f"\n\n❌ Failed: {', '.join(failed)}"
    
    msg += "\n\n⏱ Next update in 15 minutes"
    
    send_telegram(msg)

# ============================================
# MAIN
# ============================================

def main_loop():
    print("\n🔄 Starting main loop...")
    
    today = datetime.now().strftime('%A')
    is_weekend = datetime.now().weekday() >= 5
    
    send_telegram(f"""
🚀 <b>HYBRID TRADING BOT</b>

📊 9 Symbols
📅 {today} {'🔴' if is_weekend else '🟢'}

📡 Data Sources:
   • Binance: BTC, ETH, SOL
   • Alpha Vantage: Gold, Silver, Oil
   • Yahoo Finance: NIFTY, BANKNIFTY, SENSEX

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
    print("🚀 HYBRID TRADING BOT")
    print("="*50)
    
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("🌐 Web server started")
    
    main_loop()
