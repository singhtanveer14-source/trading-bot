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
# DATA SOURCES - WORKING
# ============================================

def get_price_binance(symbol):
    """Get crypto price from Binance API"""
    try:
        # Convert symbol format
        if symbol == 'BTC-USD':
            binance_symbol = 'BTCUSDT'
        elif symbol == 'ETH-USD':
            binance_symbol = 'ETHUSDT'
        elif symbol == 'SOL-USD':
            binance_symbol = 'SOLUSDT'
        else:
            return None
        
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_symbol}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
        return None
    except Exception as e:
        print(f"  Binance error: {e}")
        return None

def get_price_coingecko(symbol):
    """Get crypto price from CoinGecko API"""
    try:
        # Map symbols
        if symbol == 'BTC-USD':
            coin_id = 'bitcoin'
        elif symbol == 'ETH-USD':
            coin_id = 'ethereum'
        elif symbol == 'SOL-USD':
            coin_id = 'solana'
        else:
            return None
        
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data[coin_id]['usd'])
        return None
    except Exception as e:
        print(f"  Coingecko error: {e}")
        return None

def get_price_yahoo(symbol):
    """Get price from Yahoo (for commodities and indices)"""
    try:
        import yfinance as yf
        df = yf.download(symbol, period='1d', interval='1m', progress=False)
        if not df.empty:
            return float(df['Close'].iloc[-1])
        return None
    except:
        return None

def get_price_alpha_vantage(symbol):
    """Get price from Alpha Vantage (for indices)"""
    try:
        # Map symbols
        alpha_symbols = {
            '^NSEI': 'NSEI',
            '^NSEBANK': 'NSEBANK',
            '^BSESN': 'BSESN'
        }
        if symbol not in alpha_symbols:
            return None
        
        # Try Yahoo first for indices
        return get_price_yahoo(symbol)
    except:
        return None

# ============================================
# SYMBOLS CONFIG
# ============================================

SYMBOLS = {
    'BTC-USD': {'name': 'Bitcoin', 'emoji': '🟢', 'type': 'crypto'},
    'ETH-USD': {'name': 'Ethereum', 'emoji': '🟣', 'type': 'crypto'},
    'SOL-USD': {'name': 'Solana', 'emoji': '🟠', 'type': 'crypto'},
    'GC=F': {'name': 'Gold', 'emoji': '🥇', 'type': 'commodity'},
    'SI=F': {'name': 'Silver', 'emoji': '🥈', 'type': 'commodity'},
    'CL=F': {'name': 'Crude Oil', 'emoji': '🛢️', 'type': 'commodity'},
    '^NSEI': {'name': 'NIFTY 50', 'emoji': '🇮🇳', 'type': 'index'},
    '^NSEBANK': {'name': 'BANKNIFTY', 'emoji': '🏦', 'type': 'index'},
    '^BSESN': {'name': 'SENSEX', 'emoji': '📊', 'type': 'index'}
}

# ============================================
# GET PRICE - MULTI SOURCE
# ============================================

def get_price(symbol, symbol_info):
    """Get price using multiple sources"""
    
    price = None
    source = None
    
    if symbol_info['type'] == 'crypto':
        # Try Binance first
        price = get_price_binance(symbol)
        source = 'Binance'
        
        # If Binance fails, try CoinGecko
        if price is None:
            price = get_price_coingecko(symbol)
            source = 'CoinGecko'
        
        # If all fail, try Yahoo
        if price is None:
            price = get_price_yahoo(symbol)
            source = 'Yahoo'
    
    elif symbol_info['type'] in ['commodity', 'index']:
        # Try Yahoo first
        price = get_price_yahoo(symbol)
        source = 'Yahoo'
    
    return price, source

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
    
    for symbol, info in SYMBOLS.items():
        try:
            print(f"  Fetching {info['name']}...")
            
            price, source = get_price(symbol, info)
            
            if price:
                success_count += 1
                if info['type'] == 'index':
                    prices.append(f"{info['emoji']} {info['name']}: {price:,.2f} [{source}]")
                else:
                    prices.append(f"{info['emoji']} {info['name']}: ${price:,.2f} [{source}]")
                print(f"    ✅ ${price:,.2f} ({source})")
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
        msg += "⚠️ No prices fetched\n"
        msg += "\nPossible issues:\n"
        msg += "• Yahoo Finance may be blocking Render IP\n"
        msg += "• Trying alternative sources..."
    
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

📊 Monitoring 9 symbols
🔄 Multi-source data:
   • Binance (Crypto)
   • CoinGecko (Crypto)  
   • Yahoo (Commodities/Indices)

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
