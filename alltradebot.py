import os
import sys
import time
import threading
import requests
from datetime import datetime
from flask import Flask

# ============================================
# CREDENTIALS - HARDCODED FOR MAX SPEED
# ============================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = "-1003971188413"  # HARDCODED - YOUR GROUP ID

print(f"TOKEN: {TELEGRAM_TOKEN[:20] if TELEGRAM_TOKEN else 'MISSING'}...")
print(f"CHAT_ID: {TELEGRAM_CHAT_ID}")

if not TELEGRAM_TOKEN:
    print("❌ NO TOKEN!")
    sys.exit(1)

# ============================================
# FLASK APP
# ============================================

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is Running!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/send')
def send_test():
    """Send test message - THIS WILL WORK!"""
    try:
        print(f"📤 Sending to chat: {TELEGRAM_CHAT_ID}")
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': f"🤖 Bot is ALIVE! Time: {datetime.now().strftime('%H:%M:%S')}",
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, data=data, timeout=10)
        print(f"📡 Status: {response.status_code}")
        print(f"📡 Response: {response.text[:200]}")
        
        if response.status_code == 200:
            return "✅ Message sent! Check Telegram!"
        else:
            return f"❌ Error {response.status_code}: {response.text[:100]}", 500
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return f"❌ Exception: {e}", 500

@app.route('/force-start')
def force_start():
    """Force start with multiple messages"""
    results = []
    for i in range(3):
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': f"📊 Test {i+1}/3 - Bot Active! {datetime.now().strftime('%H:%M:%S')}",
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            results.append(f"Test {i+1}: {response.status_code}")
        except Exception as e:
            results.append(f"Test {i+1}: Error")
    
    return f"✅ Results: {', '.join(results)}"

# ============================================
# BACKGROUND TASK
# ============================================

def send_periodic_message():
    """Send heartbeat every 60 seconds"""
    count = 0
    print("🔄 Heartbeat thread started!")
    
    while True:
        try:
            time.sleep(60)  # 1 minute
            count += 1
            
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': f"❤️ Heartbeat #{count} - {datetime.now().strftime('%H:%M:%S')}"
            }
            response = requests.post(url, data=data, timeout=5)
            print(f"✅ Heartbeat {count} sent - Status: {response.status_code}")
            
        except Exception as e:
            print(f"❌ Heartbeat error: {e}")

# ============================================
# START
# ============================================

print("🚀 Starting bot...")
print(f"📱 Chat ID: {TELEGRAM_CHAT_ID}")

# Start background thread
thread = threading.Thread(target=send_periodic_message, daemon=True)
thread.start()
print("✅ Background thread started")

print("🌐 Flask running on port " + os.environ.get("PORT", "5000"))
