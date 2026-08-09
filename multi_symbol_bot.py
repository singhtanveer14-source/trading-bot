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

print("🚀 Starting Professional Trading Bot...")
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
    return "✅ Scan started! Real prices in 2-3 minutes."

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
# RELIABLE DATA SOURCES - NO ESTIMATES!
# ============================================

def get_alpha_vantage(symbol):
    """Get REAL price from Alpha Vantage"""
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
            
            # Check for API errors
            if 'Error Message' in data:
                print(f"    API Error: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                print(f"    Rate Limit: {data['Note'][:50]}")
                return None
            
            if 'Global Quote' in data and '05. price' in data['Global Quote']:
                price = data['Global Quote']['05. price']
                if price and float(price) > 0:
                    return float(price)
        return None
    except Exception as e:
        print(f"    Alpha Vantage error: {e}")
        return None

def get_binance(symbol):
    """Get REAL crypto price from Binance"""
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
            price = float(response.json()['price'])
            if price > 0:
                return price
        return None
    except:
        return None

def get_coingecko(symbol):
    """Get REAL crypto price from CoinGecko"""
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
            price = float(data[mapping[symbol]]['usd'])
            if price > 0:
                return price
        return None
    except:
        return None

def get_gold_price():
    """Get REAL Gold price from multiple sources"""
    # Source 1: Gold-API
    try:
        url = "https://api.gold-api.com/price/XAU"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'price' in data and float(data['price']) > 0:
                return float(data['price'])
    except:
        pass
    
    # Source 2: Alpha Vantage (using XAUUSD)
    try:
        price = get_alpha_vantage('XAUUSD')
        if price and price > 0:
            return price
    except:
        pass
    
    return None

def get_silver_price():
    """Get REAL Silver price"""
    try:
        url = "https://api.gold-api.com/price/XAG"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'price' in data and float(data['price']) > 0:
                return float(data['price'])
    except:
        pass
    
    try:
        price = get_alpha_vantage('XAGUSD')
        if price and price > 0:
            return price
    except:
        pass
    
    return None

def get_oil_price():
    """Get REAL Oil price from Alpha Vantage"""
    try:
        price = get_alpha_vantage('CL')
        if price and price > 0:
            return price
    except:
        pass
    return None

def get_nifty_price():
    """Get REAL NIFTY price from Alpha Vantage"""
    try:
        price = get_alpha_vantage('NSEI')
        if price and price > 0:
            return price
    except:
        pass
    return None

def get_banknifty_price():
    """Get REAL BANKNIFTY price"""
    try:
        price = get_alpha_vantage('NSEBANK')
        if price and price > 0:
            return price
    except:
        pass
    return None

def get_sensex_price():
    """Get REAL SENSEX price"""
    try:
        price = get_alpha_vantage('BSESN')
        if price and price > 0:
            return price
    except:
        pass
    return None

# ============================================
# SYMBOLS WITH DEDICATED FETCHERS
# ============================================

SYMBOLS = [
    {
        'key': 'BTC', 
        'name': 'Bitcoin', 
        'emoji': '🟢',
        'fetcher': lambda: get_binance('BTC') or get_coingecko('BTC') or get_alpha_vantage('BTCUSD')
    },
    {
        'key': 'ETH', 
        'name': 'Ethereum', 
        'emoji': '🟣',
        'fetcher': lambda: get_binance('ETH') or get_coingecko('ETH') or get_alpha_vantage('ETHUSD')
    },
    {
        'key': 'SOL', 
        'name': 'Solana', 
        'emoji': '🟠',
        'fetcher': lambda: get_binance('SOL') or get_coingecko('SOL') or get_alpha_vantage('SOLUSD')
    },
    {
        'key': 'GOLD', 
        'name': 'Gold', 
        'emoji': '🥇',
        'fetcher': get_gold_price
    },
    {
        'key': 'SILVER', 
        'name': 'Silver', 
        'emoji': '🥈',
        'fetcher': get_silver_price
    },
    {
        'key': 'OIL', 
        'name': 'Crude Oil', 
        'emoji': '🛢️',
        'fetcher': get_oil_price
    },
    {
        'key': 'NIFTY', 
        'name': 'NIFTY 50', 
        'emoji': '🇮🇳',
        'fetcher': get_nifty_price
    },
    {
        'key': 'BANKNIFTY', 
        'name': 'BANKNIFTY', 
        'emoji': '🏦',
        'fetcher': get_banknifty_price
    },
    {
        'key': 'SENSEX', 
        'name': 'SENSEX', 
        'emoji': '📊',
        'fetcher': get_sensex_price
    }
]

# ============================================
# SCAN AND SEND - ONLY REAL DATA
# ============================================

def scan_and_send():
    print(f"\n📊 Scanning at {datetime.now().strftime('%H:%M:%S')}")
    
    prices = []
    failed = []
    success_count = 0
    
    send_telegram(f"🔄 Fetching real market data... ({datetime.now().strftime('%H:%M')})")
    
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
                print(f"    ✅ Real price: {price:,.2f}")
            else:
                failed.append(info['name'])
                print(f"    ❌ No real price available")
                
        except Exception as e:
            failed.append(info['name'])
            print(f"    ❌ Error: {e}")
        
        time.sleep(12)
    
    # Build message
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    msg = "📊 <b>REAL MARKET DATA</b>\n"
    msg += f"⏱ {now}\n"
    msg += "="*40 + "\n\n"
    
    if prices:
        msg += "\n".join(prices)
        msg += f"\n\n✅ Updated: {success_count}/{len(SYMBOLS)} symbols"
    else:
        msg += "⚠️ No real prices available"
        msg += "\n\nPossible issues:"
        msg += "\n• Alpha Vantage rate limit (5/min)"
        msg += "\n• API key may need upgrade"
        msg += "\n• Market may be closed"
    
    if failed:
        msg += f"\n\n❌ Failed: {', '.join(failed)}"
    
    msg += "\n\n⏱ Next update in 15 minutes"
    
    send_telegram(msg)

# ============================================
# MAIN LOOP
# ============================================

def main_loop():
    print("\n🔄 Starting main loop...")
    
    send_telegram("""
🚀 <b>PROFESSIONAL TRADING BOT</b>

📊 Monitoring 9 symbols with REAL prices
📡 Data Sources:
   • Alpha Vantage (All assets)
   • Binance (Crypto)
   • CoinGecko (Crypto)
   • Gold-API (Precious metals)

⚠️ <b>NO ESTIMATES</b> - Only real market data

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
