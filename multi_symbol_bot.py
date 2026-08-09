import os
import sys
import time
import threading
import requests
import json
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
# DATA SOURCES - ALL SYMBOLS
# ============================================

def get_crypto_price(symbol):
    """Get crypto price from Binance"""
    try:
        binance_map = {
            'BTC-USD': 'BTCUSDT',
            'ETH-USD': 'ETHUSDT', 
            'SOL-USD': 'SOLUSDT'
        }
        if symbol not in binance_map:
            return None
        
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_map[symbol]}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
        return None
    except:
        return None

def get_gold_price():
    """Get Gold price from multiple sources"""
    try:
        # Source 1: Gold API
        url = "https://api.gold-api.com/price/XAU"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
    except:
        pass
    
    try:
        # Source 2: Kitco
        url = "https://www.kitco.com/kitco-gold-api/current?asset=gold"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data.get('ask', 0))
    except:
        pass
    
    return None

def get_silver_price():
    """Get Silver price"""
    try:
        url = "https://api.gold-api.com/price/XAG"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
    except:
        pass
    
    try:
        # Alternative source
        url = "https://www.kitco.com/kitco-gold-api/current?asset=silver"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data.get('ask', 0))
    except:
        pass
    
    return None

def get_oil_price():
    """Get Crude Oil price"""
    try:
        # Free Oil price API
        url = "https://api.energy.com/oil/price"
        # Fallback to Yahoo
        import yfinance as yf
        df = yf.download('CL=F', period='1d', interval='1m', progress=False)
        if not df.empty:
            return float(df['Close'].iloc[-1])
    except:
        pass
    return None

def get_index_price(symbol):
    """Get index prices from free sources"""
    try:
        # For NIFTY 50
        if symbol == '^NSEI':
            url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050"
            # Use Yahoo as fallback
            import yfinance as yf
            df = yf.download('^NSEI', period='1d', interval='1m', progress=False)
            if not df.empty:
                return float(df['Close'].iloc[-1])
        
        elif symbol == '^NSEBANK':
            import yfinance as yf
            df = yf.download('^NSEBANK', period='1d', interval='1m', progress=False)
            if not df.empty:
                return float(df['Close'].iloc[-1])
        
        elif symbol == '^BSESN':
            import yfinance as yf
            df = yf.download('^BSESN', period='1d', interval='1m', progress=False)
            if not df.empty:
                return float(df['Close'].iloc[-1])
    except:
        pass
    return None

# ============================================
# SYMBOLS CONFIG
# ============================================

SYMBOLS = {
    'BTC-USD': {'name': 'Bitcoin', 'emoji': '🟢', 'fetcher': get_crypto_price},
    'ETH-USD': {'name': 'Ethereum', 'emoji': '🟣', 'fetcher': get_crypto_price},
    'SOL-USD': {'name': 'Solana', 'emoji': '🟠', 'fetcher': get_crypto_price},
    'XAUUSD': {'name': 'Gold', 'emoji': '🥇', 'fetcher': get_gold_price},
    'XAGUSD': {'name': 'Silver', 'emoji': '🥈', 'fetcher': get_silver_price},
    'USOIL': {'name': 'Crude Oil', 'emoji': '🛢️', 'fetcher': get_oil_price},
    '^NSEI': {'name': 'NIFTY 50', 'emoji': '🇮🇳', 'fetcher': get_index_price},
    '^NSEBANK': {'name': 'BANKNIFTY', 'emoji': '🏦', 'fetcher': get_index_price},
    '^BSESN': {'name': 'SENSEX', 'emoji': '📊', 'fetcher': get_index_price}
}

# ============================================
# SCAN AND SEND
# ============================================

def scan_and_send():
    print(f"\n📊 Scanning at {datetime.now().strftime('%H:%M:%S')}")
    
    prices = []
    errors = []
    success_count = 0
    
    for symbol, info in SYMBOLS.items():
        try:
            print(f"  Fetching {info['name']}...")
            
            price = info['fetcher'](symbol)
            
            if price:
                success_count += 1
                if symbol in ['^NSEI', '^NSEBANK', '^BSESN']:
                    prices.append(f"{info['emoji']} {info['name']}: {price:,.2f}")
                else:
                    prices.append(f"{info['emoji']} {info['name']}: ${price:,.2f}")
                print(f"    ✅ {price:,.2f}")
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
