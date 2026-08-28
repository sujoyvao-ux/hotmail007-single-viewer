from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import re
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

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

# ============= ইমেইল ফেচ (সরাসরি টোকেন দিয়ে) =============
def fetch_emails_with_token(access_token, limit=5):
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        # ইউজার ইনফো
        user_res = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        if user_res.status_code != 200:
            return {"error": f"টোকেন বৈধ নয় (Status: {user_res.status_code})", "status": user_res.status_code}
        
        user_data = user_res.json()
        user_name = user_data.get("displayName") or user_data.get("userPrincipalName", "Unknown")
        email = user_data.get("userPrincipalName") or user_data.get("mail", "Unknown")
        
        # ইমেইল ফেচ (শেষ ৫টি)
        url = "https://graph.microsoft.com/v1.0/me/mailfolders/inbox/messages"
        params = {
            "$top": limit,
            "$select": "subject,bodyPreview,from,receivedDateTime",
            "$orderby": "receivedDateTime desc"
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            return {"error": f"ইমেইল ফেচ করতে পারেনি (Status: {response.status_code})", "status": response.status_code}
        
        emails = response.json().get("value", [])
        
        result = []
        for email_item in emails:
            subject = email_item.get('subject', '')
            preview = email_item.get('bodyPreview', '')
            from_addr = email_item.get('from', {}).get('emailAddress', {}).get('address', 'Unknown')
            received = email_item.get('receivedDateTime', '')
            
            full_text = subject + " " + preview
            otp = extract_otp(full_text)
            
            # সময় ফরম্যাট
            try:
                dt = datetime.fromisoformat(received.replace('Z', '+00:00'))
                time_str = dt.strftime('%d %b %Y, %I:%M %p')
            except:
                time_str = received
            
            result.append({
                'from': from_addr,
                'subject': subject,
                'preview': preview[:300] if preview else '',
                'received': time_str,
                'otp': otp if otp else None,
                'has_otp': otp is not None
            })
        
        return {
            'success': True,
            'user': user_name,
            'email': email,
            'total': len(result),
            'emails': result
        }
        
    except Exception as e:
        return {"error": str(e)}

# ============= ক্রেডেনশিয়াল পার্স =============
def parse_credential(cred_string):
    """
    ফরম্যাট: email:password:access_token:refresh_token
    """
    parts = cred_string.strip().split(':')
    
    if len(parts) >= 4:
        return {
            'email': parts[0],
            'password': parts[1],
            'access_token': parts[2],
            'refresh_token': parts[3]
        }
    elif len(parts) == 3:
        return {
            'email': parts[0],
            'password': parts[1],
            'access_token': parts[2],
            'refresh_token': None
        }
    else:
        return None

# ============= API - ইমেইল ফেচ =============
@app.route('/api/fetch', methods=['POST'])
def fetch_emails_api():
    data = request.json
    credential = data.get('credential', '').strip()
    limit = data.get('limit', 5)
    
    if not credential:
        return jsonify({'error': 'ক্রেডেনশিয়াল দিন'})
    
    # ক্রেডেনশিয়াল পার্স
    parsed = parse_credential(credential)
    
    if not parsed:
        return jsonify({'error': 'ভুল ফরম্যাট। ব্যবহার করুন: email:password:access_token:refresh_token'})
    
    access_token = parsed.get('access_token')
    refresh_token = parsed.get('refresh_token')
    
    if not access_token:
        return jsonify({'error': 'টোকেন পাওয়া যায়নি'})
    
    # টোকেন দিয়ে ইমেইল ফেচ
    result = fetch_emails_with_token(access_token, limit)
    
    if result.get('success'):
        # refresh_token সংরক্ষণ
        result['refresh_token'] = refresh_token
        return jsonify(result)
    else:
        return jsonify(result)

# ============= হোম পেজ =============
@app.route('/')
def home():
    return send_file('panel.html')

# ============= সার্ভার রান =============
if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║   📧 Email OTP Reader - Direct Token Method            ║
    ║   Server running at: http://localhost:5000             ║
    ║                                                         ║
    ║   📝 ফরম্যাট:                                           ║
    ║   email:password:access_token:refresh_token             ║
    ║                                                         ║
    ║   ⚠️ শুধুমাত্র আপনার নিজের অ্যাকাউন্ট ব্যবহার করুন    ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0.0', port=5000)
