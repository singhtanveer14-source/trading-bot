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
# PRICE CACHE - STORES LAST TRADED PRICE
# ============================================

price_cache = {}
cache_time = {}

def update_cache(symbol, price):
    """Update cached price"""
    price_cache[symbol] = price
    cache_time[symbol] = datetime.now()

def get_cached_price(symbol):
    """Get cached price if available"""
    if symbol in price_cache:
        return price_cache[symbol]
    return None

def get_cache_time(symbol):
    """Get when price was cached"""
    if symbol in cache_time:
        return cache_time[symbol]
    return None

# ============================================
# PART 1: ALPHA VANTAGE - WORKING SYMBOLS
# ============================================

def get_alpha_vantage(symbol):
    """Get price from Alpha Vantage"""
    try:
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': symbol,
            'apikey': ALPHA_VANTAGE_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'Global Quote' in data and '05. price' in data['Global Quote']:
                return float(data['Global Quote']['05. price'])
        return None
    except:
        return None

def get_binance(symbol):
    """Get crypto from Binance"""
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
    """Get crypto from CoinGecko"""
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

def get_gold_price():
    """Gold from Alpha Vantage"""
    try:
        price = get_alpha_vantage('XAUUSD')
        if price:
            update_cache('GOLD', price)
            return price
        return get_cached_price('GOLD')
    except:
        return get_cached_price('GOLD')

def get_silver_price():
    """Silver from Alpha Vantage"""
    try:
        price = get_alpha_vantage('XAGUSD')
        if price:
            update_cache('SILVER', price)
            return price
        return get_cached_price('SILVER')
    except:
        return get_cached_price('SILVER')

# ============================================
# PART 2: YAHOO FINANCE - WEEKDAY SYMBOLS WITH CACHE
# ============================================

def is_weekday():
    """Check if today is a weekday (Monday-Friday)"""
    today = datetime.now().weekday()
    return today < 5

def get_yfinance_price(symbol, cache_key):
    """Get price from Yahoo Finance with caching"""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            price = data['Close'].iloc[-1]
            if price and price > 0:
                price = float(price)
                update_cache(cache_key, price)
                return price
        
        # Try longer period
        data = ticker.history(period="5d", interval="1h")
        if not data.empty:
            price = data['Close'].iloc[-1]
            if price and price > 0:
                price = float(price)
                update_cache(cache_key, price)
                return price
        
        # Return cached price if available
        cached = get_cached_price(cache_key)
        if cached:
            return cached
        return None
    except Exception as e:
        print(f"    Yahoo error: {e}")
        return get_cached_price(cache_key)

def get_oil_price():
    """Crude Oil from Yahoo with cache"""
    return get_yfinance_price('CL=F', 'OIL')

def get_nifty_price():
    """NIFTY 50 from Yahoo with cache"""
    return get_yfinance_price('^NSEI', 'NIFTY')

def get_banknifty_price():
    """BANKNIFTY from Yahoo with cache"""
    return get_yfinance_price('^NSEBANK', 'BANKNIFTY')

def get_sensex_price():
    """SENSEX from Yahoo with cache"""
    return get_yfinance_price('^BSESN', 'SENSEX')

# ============================================
# SYMBOLS - HYBRID APPROACH
# ============================================

SYMBOLS = [
    # PART 1: Alpha Vantage (Working 24/7)
    {'key': 'BTC', 'name': 'Bitcoin', 'emoji': '🟢', 'fetcher': lambda: get_binance('BTC') or get_coingecko('BTC') or get_alpha_vantage('BTCUSD')},
    {'key': 'ETH', 'name': 'Ethereum', 'emoji': '🟣', 'fetcher': lambda: get_binance('ETH') or get_coingecko('ETH') or get_alpha_vantage('ETHUSD')},
    {'key': 'SOL', 'name': 'Solana', 'emoji': '🟠', 'fetcher': lambda: get_binance('SOL') or get_coingecko('SOL') or get_alpha_vantage('SOLUSD')},
    {'key': 'GOLD', 'name': 'Gold', 'emoji': '🥇', 'fetcher': get_gold_price},
    {'key': 'SILVER', 'name': 'Silver', 'emoji': '🥈', 'fetcher': get_silver_price},
    
    # PART 2: Yahoo Finance (Weekdays Only with Cache)
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
    weekday_status = "🟢 Markets Open" if is_weekday() else "🔴 Markets Closed (Sunday)"
    print(f"📅 Today: {today} - {weekday_status}")
    
    prices = []
    failed = []
    cached_items = []
    success_count = 0
    
    send_telegram(f"🔄 Market Data | {today} | {weekday_status}")
    
    for info in SYMBOLS:
        try:
            print(f"  Fetching {info['name']}...")
            price = info['fetcher']()
            
            # Check if this is cached data
            is_cached = False
            cache_time_val = get_cache_time(info['key'])
            if cache_time_val:
                age = (datetime.now() - cache_time_val).total_seconds() / 3600
                if age > 1:  # If older than 1 hour
                    is_cached = True
            
            if price and price > 0:
                success_count += 1
                
                # Format the display
                if info['key'] in ['NIFTY', 'BANKNIFTY', 'SENSEX']:
                    price_str = f"{info['emoji']} {info['name']}: {price:,.2f}"
                else:
                    price_str = f"{info['emoji']} {info['name']}: ${price:,.2f}"
                
                # Add cached indicator for weekday symbols on weekend
                if info['key'] in ['OIL', 'NIFTY', 'BANKNIFTY', 'SENSEX'] and not is_weekday():
                    cache_time_val = get_cache_time(info['key'])
                    if cache_time_val:
                        time_str = cache_time_val.strftime('%H:%M')
                        price_str += f" 📊 (Last: {time_str})"
                        cached_items.append(info['name'])
                
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
    msg += f"📅 {today} | {weekday_status}\n"
    msg += "="*40 + "\n\n"
    
    if prices:
        msg += "\n".join(prices)
        msg += f"\n\n✅ Updated: {success_count}/{len(SYMBOLS)} symbols"
    else:
        msg += "⚠️ No prices available"
    
    if cached_items:
        msg += f"\n\n📊 Showing Last Traded Price: {', '.join(cached_items)}"
    
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
    weekday_status = "🟢 Markets Open" if is_weekday() else "🔴 Markets Closed (Sunday)"
    
    send_telegram(f"""
🚀 <b>HYBRID TRADING BOT</b>

📊 9 Symbols
📅 {today} | {weekday_status}

📡 Data Sources:
   • Alpha Vantage: BTC, ETH, SOL, Gold, Silver ✅
   • Yahoo Finance: NIFTY, BANKNIFTY, SENSEX, Crude Oil {'✅' if is_weekday() else '📊 (Last Traded Price)'}

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
