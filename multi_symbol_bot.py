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

print("🚀 Starting Professional Bot...")
print(f"Token: {'✅ Found' if TELEGRAM_TOKEN else '❌ Missing'}")

if not TELEGRAM_TOKEN:
    print("❌ No token!")
    sys.exit(1)

# ============================================
# API KEYS
# ============================================

ALPHA_VANTAGE_API_KEY = "I9P5WDYIMQHADXV0"

# ============================================
# FLASK APP
# ============================================

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Professional Trading Bot is Running!"

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
    return "✅ Scan started! Check Telegram."

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
# DATA SOURCES - RELIABLE & FREE
# ============================================

def get_alpha_vantage(symbol):
    """Alpha Vantage - Most reliable for all assets"""
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
    """Binance - Best for crypto"""
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
    """CoinGecko - Crypto backup"""
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
    """Gold - Multiple sources"""
    # Try Gold-API
    try:
        url = "https://api.gold-api.com/price/XAU"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
    except:
        pass
    # Try Alpha Vantage
    return get_alpha_vantage('XAUUSD')

def get_silver_price():
    """Silver - Multiple sources"""
    try:
        url = "https://api.gold-api.com/price/XAG"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
    except:
        pass
    return get_alpha_vantage('XAGUSD')

def get_oil_price():
    """Oil from Alpha Vantage"""
    return get_alpha_vantage('CL')

def get_nifty_price():
    """NIFTY from Alpha Vantage"""
    return get_alpha_vantage('NSEI')

def get_banknifty_price():
    """BANKNIFTY from Alpha Vantage"""
    return get_alpha_vantage('NSEBANK')

def get_sensex_price():
    """SENSEX from Alpha Vantage"""
    return get_alpha_vantage('BSESN')

# ============================================
# SYMBOLS
# ============================================

SYMBOLS = [
    {'key': 'BTC', 'name': 'Bitcoin', 'emoji': '🟢', 'fetcher': lambda: get_binance('BTC') or get_coingecko('BTC') or get_alpha_vantage('BTCUSD')},
    {'key': 'ETH', 'name': 'Ethereum', 'emoji': '🟣', 'fetcher': lambda: get_binance('ETH') or get_coingecko('ETH') or get_alpha_vantage('ETHUSD')},
    {'key': 'SOL', 'name': 'Solana', 'emoji': '🟠', 'fetcher': lambda: get_binance('SOL') or get_coingecko('SOL') or get_alpha_vantage('SOLUSD')},
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
    
    prices = []
    failed = []
    success_count = 0
    
    send_telegram(f"🔄 Fetching market data... ({datetime.now().strftime('%H:%M')})")
    
    for info in SYMBOLS:
        try:
            print(f"  Fetching {info['name']}...")
            price = info['fetcher']()
            
            if price and price > 0:
                success_count += 1
                if info['key'] in ['NIFTY', 'BANKNIFTY', 'SENSEX']:
                    prices.append(f"{info['emoji']} {info['name']}: {price:,.2f}")
                else:
                    prices.append(f"{info['emoji']} {info['name']}: ${price:,.2f}")
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
    
    msg = "📊 <b>MARKET UPDATE</b>\n"
    msg += f"⏱ {now}\n"
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
    
    send_telegram("""
🚀 <b>PROFESSIONAL TRADING BOT</b>

📊 9 Symbols | Real Prices Only
📡 Alpha Vantage + Binance + CoinGecko
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
    print("🚀 PROFESSIONAL TRADING BOT")
    print("="*50)
    
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    print("🌐 Web server started")
    
    main_loop()
