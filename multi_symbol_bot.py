import os
import sys
import time
import threading
import requests
from datetime import datetime
from flask import Flask
import yfinance as yf
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
    return "Bot is Running!"

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
        print(f"📤 Sending...")
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
# SYMBOLS WITH WORKING TICKERS
# ============================================

SYMBOLS = {
    'BTC-USD': {'name': 'Bitcoin', 'emoji': '🟢'},
    'ETH-USD': {'name': 'Ethereum', 'emoji': '🟣'},
    'SOL-USD': {'name': 'Solana', 'emoji': '🟠'},
    'GC=F': {'name': 'Gold', 'emoji': '🥇'},
    'SI=F': {'name': 'Silver', 'emoji': '🥈'},
    'CL=F': {'name': 'Crude Oil', 'emoji': '🛢️'},
}

# Add indices - using different approach
# NIFTY and BANKNIFTY often fail, so we'll try alternative symbols
INDEX_SYMBOLS = {
    '^NSEI': {'name': 'NIFTY 50', 'emoji': '🇮🇳'},
    '^NSEBANK': {'name': 'BANKNIFTY', 'emoji': '🏦'},
    '^BSESN': {'name': 'SENSEX', 'emoji': '📊'}
}

# ============================================
# FETCH PRICE WITH FALLBACK
# ============================================

def fetch_price(symbol):
    """Fetch price with fallback methods"""
    try:
        # Try with 2 days of 1h data
        df = yf.download(symbol, period='2d', interval='1h', progress=False)
        if not df.empty:
            return float(df['Close'].iloc[-1])
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

def fetch_index_price(symbol):
    """Special handling for indices"""
    try:
        # Try with 5 days daily data
        df = yf.download(symbol, period='5d', interval='1d', progress=False)
        if not df.empty:
            return float(df['Close'].iloc[-1])
        return None
    except Exception as e:
        print(f"  Index error: {e}")
        return None

# ============================================
# SCAN FUNCTION
# ============================================

def scan_and_send(force=False):
    print(f"\n📊 Scanning at {datetime.now().strftime('%H:%M:%S')}")
    
    prices = []
    errors = []
    
    # 1. Scan Crypto & Commodities
    for symbol, info in SYMBOLS.items():
        try:
            print(f"  Fetching {info['name']} ({symbol})...")
            price = fetch_price(symbol)
            
            if price:
                prices.append(f"{info['emoji']} {info['name']}: ${price:,.2f}")
                print(f"    ✅ ${price:,.2f}")
            else:
                errors.append(f"❌ {info['name']}: No data")
                print(f"    ❌ No data")
                
        except Exception as e:
            errors.append(f"❌ {info['name']}: {str(e)[:30]}")
            print(f"    ❌ {e}")
        
        time.sleep(0.3)
    
    # 2. Scan Indices
    for symbol, info in INDEX_SYMBOLS.items():
        try:
            print(f"  Fetching {info['name']} ({symbol})...")
            price = fetch_index_price(symbol)
            
            if price:
                prices.append(f"{info['emoji']} {info['name']}: {price:,.2f}")
                print(f"    ✅ {price:,.2f}")
            else:
                errors.append(f"❌ {info['name']}: No data")
                print(f"    ❌ No data")
                
        except Exception as e:
            errors.append(f"❌ {info['name']}: {str(e)[:30]}")
            print(f"    ❌ {e}")
        
        time.sleep(0.3)
    
    # 3. Build and send message
    msg = "📊 MARKET UPDATE\n"
    msg += f"⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    msg += "="*35 + "\n\n"
    
    if prices:
        msg += "\n".join(prices)
        msg += f"\n\n✅ {len(prices)} symbols updated"
    else:
        msg += "⚠️ No prices fetched. Retrying..."
    
    if errors:
        msg += f"\n\n⚠️ Errors: {len(errors)}"
    
    msg += "\n\n⏱ Next update in 15 minutes"
    
    send_telegram(msg)

# ============================================
# MAIN LOOP
# ============================================

def main_loop():
    print("\n🔄 Starting main loop...")
    
    # Send startup
    send_telegram("🚀 Bot Started!\n\nMonitoring 6 Crypto/Commodities + 3 Indices\nUpdates every 15 minutes\n\nUse /scan to force update")
    
    # First scan after 3 seconds
    print("⏳ Waiting 3 seconds...")
    time.sleep(3)
    scan_and_send()
    
    # Loop
    loop_count = 0
    while True:
        time.sleep(900)  # 15 minutes
        loop_count += 1
        print(f"\n🔄 Loop #{loop_count}")
        scan_and_send()

# ============================================
# RUN
# ============================================

if __name__ == "__main__":
    print("="*50)
    print("🚀 MULTI-SYMBOL BOT")
    print("="*50)
    
    # Start web server
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("🌐 Web server started")
    
    # Start main loop
    main_loop()
