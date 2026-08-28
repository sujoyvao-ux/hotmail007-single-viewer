from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import re
import json
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# ============= কনফিগারেশন =============
API_KEY = os.environ.get('API_KEY', 'your_api_key_here')
BASE_URL = os.environ.get('BASE_URL', 'https://gapi.hotmail007.com')

# ============= OTP এক্সট্র্যাক্ট =============
def extract_otp(text):
    if not text:
        return None
    patterns = [
        r'\b(\d{6})\b',
        r'\b(\d{4})\b',
        r'OTP[:\s]*(\d{4,6})',
        r'code[:\s]*(\d{4,6})',
        r'verification[:\s]*(\d{4,6})',
        r'(\d{3}\s?\d{3})',
        r'(\d{3}-\d{3})'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).replace(' ', '').replace('-', '')
    return None

# ============= API কল ফাংশন =============
def call_api(endpoint, params=None):
    """Hotmail007 API তে কল করে"""
    url = f"{BASE_URL}{endpoint}"
    if params is None:
        params = {}
    if 'clientKey' not in params:
        params['clientKey'] = API_KEY
    
    try:
        response = requests.get(url, params=params, timeout=30)
        return response.json()
    except Exception as e:
        return {'error': str(e), 'success': False}

# ============= ব্যালেন্স চেক =============
@app.route('/api/balance')
def get_balance():
    result = call_api('/open/balance')
    return jsonify(result)

# ============= স্টক চেক =============
@app.route('/api/stock')
def get_stock():
    product_id = request.args.get('productId')
    params = {}
    if product_id:
        params['productId'] = product_id
    result = call_api('/open/stock', params)
    return jsonify(result)

# ============= ইমেইল ফেচ (সরাসরি API দিয়ে) =============
@app.route('/api/mail/latest', methods=['POST'])
def get_latest_mail():
    data = request.json
    account = data.get('account', '').strip()
    folder = data.get('folder', 'inbox')
    limit = data.get('limit', 5)
    start_timestamp = data.get('start_timestamp')
    
    if not account:
        return jsonify({'error': 'অ্যাকাউন্ট দিন', 'success': False})
    
    # একাধিক ইমেইল পেতে বারবার কল
    emails = []
    params = {
        'account': account,
        'folder': folder
    }
    if start_timestamp:
        params['start_timestamp'] = start_timestamp
    
    # API তে কয়েকবার কল করে ইমেইল সংগ্রহ
    for i in range(limit):
        result = call_api('/open/mail/latest', params)
        
        if result.get('success') and result.get('data'):
            email_data = result['data']
            # OTP এক্সট্র্যাক্ট
            full_text = email_data.get('subject', '') + " " + email_data.get('text', '') + " " + email_data.get('html', '')
            otp = extract_otp(full_text)
            
            emails.append({
                'from': email_data.get('from', 'Unknown'),
                'subject': email_data.get('subject', 'No Subject'),
                'text': email_data.get('text', '')[:300],
                'html': email_data.get('html', ''),
                'receivedAt': email_data.get('receivedAt', ''),
                'otp': otp if otp else None,
                'has_otp': otp is not None
            })
            
            # পরবর্তী ইমেইলের জন্য start_timestamp আপডেট
            if email_data.get('receivedAt'):
                try:
                    dt = datetime.fromisoformat(email_data['receivedAt'].replace('Z', '+00:00'))
                    params['start_timestamp'] = int(dt.timestamp())
                except:
                    pass
        else:
            break
    
    return jsonify({
        'success': True,
        'total': len(emails),
        'emails': emails,
        'account': account
    })

# ============= অর্ডার লিস্ট =============
@app.route('/api/orders')
def get_orders():
    page_num = request.args.get('pageNum', 1)
    page_size = request.args.get('pageSize', 10)
    status = request.args.get('status')
    
    params = {
        'pageNum': page_num,
        'pageSize': page_size
    }
    if status:
        params['status'] = status
    
    result = call_api('/open/orders', params)
    return jsonify(result)

# ============= লেগ্যাসি ইমেইল ফেচ =============
@app.route('/api/mail/legacy', methods=['POST'])
def get_legacy_mail():
    data = request.json
    account = data.get('account', '').strip()
    folder = data.get('folder', 'inbox')
    start_timestamp = data.get('start_timestamp')
    
    if not account:
        return jsonify({'error': 'অ্যাকাউন্ট দিন', 'success': False})
    
    params = {
        'clientKey': API_KEY,
        'account': account,
        'folder': folder
    }
    if start_timestamp:
        params['start_timestamp'] = start_timestamp
    
    try:
        url = f"{BASE_URL}/v1/mail/getFirstMail"
        response = requests.get(url, params=params, timeout=30)
        result = response.json()
        
        if result.get('success') and result.get('data'):
            email_data = result['data']
            full_text = email_data.get('subject', '') + " " + email_data.get('text', '')
            otp = extract_otp(full_text)
            
            result['data']['otp'] = otp
            result['data']['has_otp'] = otp is not None
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e), 'success': False})

# ============= অ্যাকাউন্ট ক্রয় =============
@app.route('/api/buy', methods=['POST'])
def buy_accounts():
    data = request.json
    product_id = data.get('productId')
    quantity = data.get('quantity', 1)
    
    if not product_id:
        return jsonify({'error': 'productId দিন', 'success': False})
    
    params = {
        'clientKey': API_KEY,
        'productId': product_id,
        'quantity': quantity
    }
    
    result = call_api('/open/buy', params)
    return jsonify(result)

# ============= হোম পেজ =============
@app.route('/')
def home():
    return send_file('panel.html')

# ============= সার্ভার রান =============
if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║   📧 Hotmail007 Email OTP Reader Panel                         ║
    ║   Server running at: http://localhost:5000                    ║
    ║                                                                 ║
    ║   🔑 API Key: {api_key[:20]}...                               ║
    ║   📡 Base URL: {base_url}                                     ║
    ║                                                                 ║
    ║   ⚠️ শুধুমাত্র আপনার নিজের অ্যাকাউন্ট ব্যবহার করুন            ║
    ╚══════════════════════════════════════════════════════════════════╝
    """.format(api_key=API_KEY, base_url=BASE_URL))
    app.run(debug=True, host='0.0.0.0', port=5000)
