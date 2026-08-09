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
print(f"Chat ID: {TELEGRAM_CHAT_ID}")

if not TELEGRAM_TOKEN:
    print("❌ No token!")
    sys.exit(1)

# ============================================
# ALPHA VANTAGE API KEY - YOUR KEY
# ============================================

ALPHA_VANTAGE_API_KEY = "I9P5WDYIMQHADXV0"

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

@app.route('/scan')
def force_scan():
    print("🔍 Force scan triggered!")
    scan_and_send()
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
# ALPHA VANTAGE API
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
        print(f"    Alpha Vantage: {symbol}")
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'Global Quote' in data and '05. price' in data['Global Quote']:
                price = data['Global Quote']['05. price']
                if price:
                    return float(price)
        return None
    except Exception as e:
        print(f"    Alpha Vantage error: {e}")
        return None

# ============================================
# BINANCE API (CRYPTO)
# ============================================

def get_binance(symbol):
    """Get crypto price from Binance"""
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

# ============================================
# COINGECKO API (CRYPTO BACKUP)
# ============================================

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
# SYMBOLS CONFIG
# ============================================

# Alpha Vantage symbols mapping
ALPHA_SYMBOLS = {
    'BTC': 'BTCUSD',
    'ETH': 'ETHUSD',
    'SOL': 'SOLUSD',
    'GOLD': 'XAUUSD',
    'SILVER': 'XAGUSD',
    'OIL': 'CL',
    'NIFTY': 'NSEI',
    'BANKNIFTY': 'NSEBANK',
    'SENSEX': 'BSESN'
}

SYMBOLS = {
    'BTC': {'name': 'Bitcoin', 'emoji': '🟢', 'alpha': 'BTCUSD'},
    'ETH': {'name': 'Ethereum', 'emoji': '🟣', 'alpha': 'ETHUSD'},
    'SOL': {'name': 'Solana', 'emoji': '🟠', 'alpha': 'SOLUSD'},
    'GOLD': {'name': 'Gold', 'emoji': '🥇', 'alpha': 'XAUUSD'},
    'SILVER': {'name': 'Silver', 'emoji': '🥈', 'alpha': 'XAGUSD'},
    'OIL': {'name': 'Crude Oil', 'emoji': '🛢️', 'alpha': 'CL'},
    'NIFTY': {'name': 'NIFTY 50', 'emoji': '🇮🇳', 'alpha': 'NSEI'},
    'BANKNIFTY': {'name': 'BANKNIFTY', 'emoji': '🏦', 'alpha': 'NSEBANK'},
    'SENSEX': {'name': 'SENSEX', 'emoji': '📊', 'alpha': 'BSESN'}
}

# ============================================
# FETCH PRICE - MULTI SOURCE
# ============================================

def fetch_price(key, info):
    """Fetch price using multiple sources"""
    
    price = None
    source_used = None
    
    # 1. Try Alpha Vantage first (ALL SYMBOLS)
    alpha_symbol = info['alpha']
    print(f"    Alpha Symbol: {alpha_symbol}")
    price = get_alpha_vantage(alpha_symbol)
    if price:
        source_used = 'Alpha Vantage'
        return price, source_used
    
    # 2. For crypto, try Binance
    if key in ['BTC', 'ETH', 'SOL']:
        price = get_binance(key)
        if price:
            source_used = 'Binance'
            return price, source_used
    
    # 3. For crypto, try CoinGecko
    if key in ['BTC', 'ETH', 'SOL']:
        price = get_coingecko(key)
        if price:
            source_used = 'CoinGecko'
            return price, source_used
    
    return None, None

# ============================================
# SCAN AND SEND
# ============================================

def scan_and_send():
    print(f"\n📊 Scanning at {datetime.now().strftime('%H:%M:%S')}")
    
    prices = []
    errors = []
    success_count = 0
    
    # Send heartbeat
    send_telegram(f"🔄 Scanning markets... ({datetime.now().strftime('%H:%M')})")
    
    for key, info in SYMBOLS.items():
        try:
            print(f"  Fetching {info['name']}...")
            
            price, source = fetch_price(key, info)
            
            if price:
                success_count += 1
                # Format differently for indices
                if key in ['NIFTY', 'BANKNIFTY', 'SENSEX']:
                    prices.append(f"{info['emoji']} {info['name']}: {price:,.2f} [{source}]")
                else:
                    prices.append(f"{info['emoji']} {info['name']}: ${price:,.2f} [{source}]")
                print(f"    ✅ {price:,.2f} ({source})")
            else:
                errors.append(f"❌ {info['name']}: No data")
                print(f"    ❌ No data")
                
        except Exception as e:
            errors.append(f"❌ {info['name']}: Error")
            print(f"    ❌ {e}")
        
        time.sleep(0.5)
    
    # Build message
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    msg = "📊 <b>MARKET UPDATE</b>\n"
    msg += f"⏱ {now}\n"
    msg += "="*40 + "\n\n"
    
    if prices:
        msg += "\n".join(prices)
        msg += f"\n\n✅ Updated: {success_count}/{len(SYMBOLS)} symbols"
    else:
        msg += "⚠️ No prices fetched"
    
    if errors and len(errors) <= 3:
        msg += "\n\n⚠️ Errors:\n" + "\n".join(errors)
    
    msg += "\n\n⏱ Next update in 15 minutes"
    
    send_telegram(msg)

# ============================================
# MAIN LOOP
# ============================================

def main_loop():
    print("\n🔄 Starting main loop...")
    
    send_telegram("""
🚀 <b>TRADING BOT STARTED</b>

📊 Monitoring 9 symbols:
🟢 Bitcoin
🟣 Ethereum
🟠 Solana
🥇 Gold
🥈 Silver
🛢️ Crude Oil
🇮🇳 NIFTY 50
🏦 BANKNIFTY
📊 SENSEX

📡 Data Sources:
   • Alpha Vantage (ALL symbols)
   • Binance (Crypto backup)
   • CoinGecko (Crypto backup)

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
