import os
import sys
import time
import threading
import requests
from datetime import datetime
from flask import Flask
import warnings
warnings.filterwarnings('ignore')

# ============================================
# TELEGRAM CREDENTIALS
# ============================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003971188413")

print("🚀 Starting Bot...")
print(f"Token: {'✅ Found' if TELEGRAM_TOKEN else '❌ Missing'}")

if not TELEGRAM_TOKEN:
    print("❌ No token!")
    sys.exit(1)

# ============================================
# ALPHA VANTAGE API
# ============================================

ALPHA_VANTAGE_API_KEY = "I9P5WDYIMQHADXV0"

# ============================================
# FLASK APP - SIMPLIFIED
# ============================================

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is Running!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/scan')
def force_scan():
    """Force scan - runs in background to avoid timeout"""
    print("🔍 Force scan triggered!")
    
    # Run scan in background thread
    def background_scan():
        try:
            scan_and_send()
        except Exception as e:
            print(f"❌ Scan error: {e}")
            send_telegram(f"⚠️ Scan error: {str(e)[:100]}")
    
    thread = threading.Thread(target=background_scan)
    thread.start()
    
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
# WORKING DATA SOURCES
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

# ============================================
# FALLBACK PRICES
# ============================================

FALLBACK_PRICES = {
    'BTC': 67000,
    'ETH': 3500,
    'SOL': 170,
    'GOLD': 2350,
    'SILVER': 28.50,
    'OIL': 82.00,
    'NIFTY': 24850,
    'BANKNIFTY': 52000,
    'SENSEX': 82000
}

# ============================================
# SYMBOLS
# ============================================

SYMBOLS = [
    {'key': 'BTC', 'name': 'Bitcoin', 'emoji': '🟢', 'alpha': 'BTCUSD'},
    {'key': 'ETH', 'name': 'Ethereum', 'emoji': '🟣', 'alpha': 'ETHUSD'},
    {'key': 'SOL', 'name': 'Solana', 'emoji': '🟠', 'alpha': 'SOLUSD'},
    {'key': 'GOLD', 'name': 'Gold', 'emoji': '🥇', 'alpha': 'XAUUSD'},
    {'key': 'SILVER', 'name': 'Silver', 'emoji': '🥈', 'alpha': 'XAGUSD'},
    {'key': 'OIL', 'name': 'Crude Oil', 'emoji': '🛢️', 'alpha': 'CL'},
    {'key': 'NIFTY', 'name': 'NIFTY 50', 'emoji': '🇮🇳', 'alpha': 'NSEI'},
    {'key': 'BANKNIFTY', 'name': 'BANKNIFTY', 'emoji': '🏦', 'alpha': 'NSEBANK'},
    {'key': 'SENSEX', 'name': 'SENSEX', 'emoji': '📊', 'alpha': 'BSESN'}
]

# ============================================
# FETCH PRICE - SIMPLE
# ============================================

def fetch_price(symbol_info):
    """Fetch price - tries multiple sources"""
    
    key = symbol_info['key']
    
    # 1. Try Alpha Vantage
    price = get_alpha_vantage(symbol_info['alpha'])
    if price:
        return price, 'Alpha Vantage'
    
    # 2. For crypto, try Binance
    if key in ['BTC', 'ETH', 'SOL']:
        price = get_binance(key)
        if price:
            return price, 'Binance'
    
    # 3. For crypto, try CoinGecko
    if key in ['BTC', 'ETH', 'SOL']:
        price = get_coingecko(key)
        if price:
            return price, 'CoinGecko'
    
    # 4. Use fallback
    if key in FALLBACK_PRICES:
        return FALLBACK_PRICES[key], '📊 Estimate'
    
    return None, None

# ============================================
# SCAN AND SEND
# ============================================

def scan_and_send():
    print(f"\n📊 Scanning at {datetime.now().strftime('%H:%M:%S')}")
    
    prices = []
    success_count = 0
    fallback_count = 0
    
    # Send start message
    send_telegram(f"🔄 Scanning markets... ({datetime.now().strftime('%H:%M')})")
    
    for info in SYMBOLS:
        try:
            print(f"  Fetching {info['name']}...")
            
            price, source = fetch_price(info)
            
            if price:
                success_count += 1
                if source == '📊 Estimate':
                    fallback_count += 1
                
                if info['key'] in ['NIFTY', 'BANKNIFTY', 'SENSEX']:
                    prices.append(f"{info['emoji']} {info['name']}: {price:,.2f} [{source}]")
                else:
                    prices.append(f"{info['emoji']} {info['name']}: ${price:,.2f} [{source}]")
                print(f"    ✅ {price:,.2f} ({source})")
            else:
                print(f"    ❌ No data")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
        
        # Wait 12 seconds between requests (Alpha Vantage rate limit)
        time.sleep(12)
    
    # Build message
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    msg = "📊 <b>MARKET UPDATE</b>\n"
    msg += f"⏱ {now}\n"
    msg += "="*40 + "\n\n"
    
    if prices:
        msg += "\n".join(prices)
        msg += f"\n\n✅ Updated: {success_count}/{len(SYMBOLS)} symbols"
        if fallback_count > 0:
            msg += f"\n⚠️ {fallback_count} symbols using estimated prices"
    else:
        msg += "⚠️ No prices fetched"
    
    msg += "\n\n⏱ Next update in 15 minutes"
    
    send_telegram(msg)

# ============================================
# MAIN LOOP
# ============================================

def main_loop():
    print("\n🔄 Starting main loop...")
    
    send_telegram("""
🚀 <b>TRADING BOT STARTED</b>

📊 Monitoring 9 symbols
📡 Data: Alpha Vantage + Binance + CoinGecko
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
    
    # Start web server
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("🌐 Web server started")
    
    # Start main loop
    main_loop()
