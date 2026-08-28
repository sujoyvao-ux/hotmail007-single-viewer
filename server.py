from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import re
import os
import sys

app = Flask(__name__)
CORS(app)

# ============= কনফিগারেশন =============
API_KEY = os.environ.get('API_KEY', '')
BASE_URL = 'https://gapi.hotmail007.com'
PORT = int(os.environ.get('PORT', 5000))

print(f"🔑 API_KEY: {'✅ সেট আছে' if API_KEY else '❌ সেট নেই'}")
print(f"📡 PORT: {PORT}")

# ============= OTP ফাইন্ডার =============
def find_otp(text):
    if not text:
        return None
    patterns = [
        r'\b(\d{6})\b',
        r'\b(\d{4})\b',
        r'OTP[:\s]*(\d{4,6})',
        r'code[:\s]*(\d{4,6})',
        r'verification[:\s]*(\d{4,6})'
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).replace(' ', '')
    return None

# ============= API: ইমেইল ফেচ =============
@app.route('/api/fetch', methods=['POST'])
def fetch_email():
    data = request.json
    account = data.get('account', '').strip()
    
    if not account:
        return jsonify({'error': 'অ্যাকাউন্ট দিন', 'success': False})
    
    if not API_KEY:
        return jsonify({'error': 'API_KEY সেট করুন। Railway তে Environment Variable যোগ করুন।', 'success': False})
    
    try:
        url = f"{BASE_URL}/open/mail/latest"
        params = {
            'clientKey': API_KEY,
            'account': account,
            'folder': 'inbox'
        }
        
        print(f"📤 Fetching email for: {account[:30]}...")
        response = requests.get(url, params=params, timeout=30)
        result = response.json()
        
        if result.get('success') and result.get('data'):
            email = result['data']
            full_text = email.get('subject', '') + " " + email.get('text', '')
            otp = find_otp(full_text)
            
            return jsonify({
                'success': True,
                'from': email.get('from', 'Unknown'),
                'subject': email.get('subject', 'No Subject'),
                'text': email.get('text', '')[:500],
                'received': email.get('receivedAt', ''),
                'otp': otp if otp else None
            })
        else:
            return jsonify({'error': 'ইমেইল পাওয়া যায়নি', 'success': False})
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'error': str(e), 'success': False})

# ============= API: ব্যালেন্স =============
@app.route('/api/balance')
def get_balance():
    if not API_KEY:
        return jsonify({'error': 'API_KEY সেট করুন', 'success': False})
    try:
        res = requests.get(f"{BASE_URL}/open/balance", params={'clientKey': API_KEY}, timeout=30)
        return jsonify(res.json())
    except Exception as e:
        return jsonify({'error': str(e), 'success': False})

# ============= হোম পেজ =============
@app.route('/')
def home():
    try:
        return send_file('panel.html')
    except Exception as e:
        return f"<h1>Error loading panel.html</h1><p>{e}</p>"

# ============= হেলথ চেক =============
@app.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'api_key_set': bool(API_KEY),
        'port': PORT
    })

# ============= Root check =============
@app.route('/ping')
def ping():
    return 'pong'

# ============= সার্ভার রান =============
if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║   📧 Email OTP Reader - Railway Ready                          ║
    ║   Server starting...                                           ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=PORT, debug=False)
