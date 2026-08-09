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
# SCAN
# ============================================

def scan_and_send():
    print(f"\n📊 Scanning at {datetime.now().strftime('%H:%M:%S')}")
    
    prices = []
    
    for symbol, name in SYMBOLS.items():
        try:
            df = yf.download(symbol, period='1d', interval='1h', progress=False)
            if df.empty:
                continue
            price = df['Close'].iloc[-1]
            prices.append(f"✅ {name}: ${price:,.2f}")
            time.sleep(0.2)
        except Exception as e:
            print(f"❌ {name}: {e}")
    
    msg = "📊 MARKET UPDATE\n"
    msg += f"⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    msg += "="*30 + "\n\n"
    msg += "\n".join(prices)
    msg += "\n\n⏱ Next update in 15 minutes"
    
    send_telegram(msg)

# ============================================
# MAIN LOOP
# ============================================

def main_loop():
    print("\n🔄 Starting loop...")
    
    # Send startup
    send_telegram("🚀 Bot Started!\n\nMonitoring 9 symbols\nUpdates every 15 minutes")
    
    # First scan
    scan_and_send()
    
    # Loop
    while True:
        time.sleep(900)  # 15 minutes
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
