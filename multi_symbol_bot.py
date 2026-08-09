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
    """Force immediate scan and send results"""
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
        print(f"📤 Sending: {message[:50]}...")
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
# SYMBOLS
# ============================================

SYMBOLS = {
    'BTC-USD': 'Bitcoin',
    'ETH-USD': 'Ethereum', 
    'SOL-USD': 'Solana',
    'GC=F': 'Gold',
    'SI=F': 'Silver',
    'CL=F': 'Oil',
    '^NSEI': 'NIFTY',
    '^NSEBANK': 'BANKNIFTY',
    '^BSESN': 'SENSEX'
}

# ============================================
# SCAN FUNCTION WITH DEBUG
# ============================================

def scan_and_send(force=False):
    print(f"\n📊 Scanning at {datetime.now().strftime('%H:%M:%S')}")
    
    # Send a heartbeat message first
    heartbeat = f"🔄 Bot is scanning... ({datetime.now().strftime('%H:%M:%S')})"
    send_telegram(heartbeat)
    
    prices = []
    errors = []
    
    for symbol, name in SYMBOLS.items():
        try:
            print(f"  Fetching {name} ({symbol})...")
            df = yf.download(symbol, period='2d', interval='1h', progress=False)
            
            if df.empty:
                errors.append(f"❌ {name}: No data")
                print(f"    ❌ No data")
                continue
                
            price = float(df['Close'].iloc[-1])
            prices.append(f"✅ {name}: ${price:,.2f}")
            print(f"    ✅ ${price:,.2f}")
            
        except Exception as e:
            error_msg = f"❌ {name}: {str(e)[:50]}"
            errors.append(error_msg)
            print(f"    ❌ {e}")
        
        time.sleep(0.3)  # Rate limit
    
    # Build message
    msg = "📊 MARKET UPDATE\n"
    msg += f"⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    msg += "="*30 + "\n\n"
    
    if prices:
        msg += "\n".join(prices)
    else:
        msg += "❌ No prices fetched"
    
    if errors:
        msg += "\n\n⚠️ Errors:\n" + "\n".join(errors[:3])
    
    msg += f"\n\n📈 {len(prices)}/{len(SYMBOLS)} symbols updated"
    msg += "\n⏱ Next update in 15 minutes"
    
    send_telegram(msg)

# ============================================
# MAIN LOOP WITH DEBUG
# ============================================

def main_loop():
    print("\n🔄 Starting main loop...")
    
    # Send startup
    send_telegram("🚀 Bot Started!\n\nMonitoring 9 symbols\nUpdates every 15 minutes\n\nTest /scan to force update")
    
    # First scan after 5 seconds (give time to initialize)
    print("⏳ Waiting 5 seconds before first scan...")
    time.sleep(5)
    scan_and_send()
    
    # Loop
    loop_count = 0
    while True:
        time.sleep(900)  # 15 minutes
        loop_count += 1
        print(f"\n🔄 Loop #{loop_count}")
        scan_and_send()
        print(f"✅ Loop #{loop_count} complete")

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
