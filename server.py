from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import re
import json
import base64
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# ============= OTP এক্সট্র্যাক্ট =============
def extract_otp(text):
    patterns = [
        r'\b(\d{6})\b',
        r'\b(\d{4})\b',
        r'OTP[:\s]*(\d{4,6})',
        r'code[:\s]*(\d{4,6})',
        r'verification[:\s]*(\d{4,6})',
        r'(\d{3}\s?\d{3})'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).replace(' ', '')
    return None

# ============= ক্রেডেনশিয়াল পার্স =============
def parse_credential(cred_string):
    """
    ফরম্যাট: email:password:access_token:refresh_token
    অথবা: email:password
    অথবা: email:access_token (পাসওয়ার্ড ছাড়া)
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
        # email:password:access_token (refresh_token নেই)
        return {
            'email': parts[0],
            'password': parts[1],
            'access_token': parts[2],
            'refresh_token': None
        }
    elif len(parts) >= 2:
        return {
            'email': parts[0],
            'password': parts[1],
            'access_token': None,
            'refresh_token': None
        }
    else:
        return None

# ============= টোকেন রিফ্রেশ =============
def refresh_access_token(refresh_token):
    try:
        url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        data = {
            "client_id": "00000000482c6b4a",
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        res = requests.post(url, data=data)
        if res.status_code == 200:
            return res.json().get('access_token')
        return None
    except:
        return None

# ============= টোকেন দিয়ে ইমেইল ফেচ =============
def fetch_emails_with_token(email, access_token):
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # ইউজার ইনফো
        user_res = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        user_name = "Unknown"
        if user_res.status_code == 200:
            data = user_res.json()
            user_name = data.get("displayName") or data.get("userPrincipalName", "Unknown")
        else:
            return {"error": f"টোকেন বৈধ নয় (Status: {user_res.status_code})"}
        
        # ইমেইল ফেচ
        url = "https://graph.microsoft.com/v1.0/me/mailfolders/inbox/messages"
        params = {
            "$top": 15,
            "$select": "subject,bodyPreview,from,receivedDateTime",
            "$orderby": "receivedDateTime desc"
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            return {"error": f"ইমেইল ফেচ করতে পারেনি (Status: {response.status_code})"}
        
        emails = response.json().get("value", [])
        
        result = []
        for email_item in emails:
            subject = email_item.get('subject', '')
            preview = email_item.get('bodyPreview', '')
            from_addr = email_item.get('from', {}).get('emailAddress', {}).get('address', 'Unknown')
            received = email_item.get('receivedDateTime', '')
            
            full_text = subject + " " + preview
            otp = extract_otp(full_text)
            
            result.append({
                'from': from_addr,
                'subject': subject,
                'preview': preview[:300],
                'received': received,
                'otp': otp if otp else '🔴 OTP খুঁজে পাওয়া যায়নি',
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

# ============= পাসওয়ার্ড দিয়ে লগইন (এখন /organizations ব্যবহার করব) =============
def login_with_password(email, password):
    try:
        # /organizations এন্ডপয়েন্ট ব্যবহার করি
        token_url = "https://login.microsoftonline.com/organizations/oauth2/v2.0/token"
        token_data = {
            "client_id": "00000000482c6b4a",
            "scope": "https://outlook.office.com/Mail.Read offline_access",
            "username": email,
            "password": password,
            "grant_type": "password"
        }
        
        token_res = requests.post(token_url, data=token_data)
        
        if token_res.status_code != 200:
            error_data = token_res.json()
            error_msg = error_data.get('error_description', 'Login failed')
            return {"error": f"লগইন ব্যর্থ: {error_msg}"}
        
        data = token_res.json()
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        
        if not access_token:
            return {"error": "টোকেন পাওয়া যায়নি"}
        
        result = fetch_emails_with_token(email, access_token)
        if result.get('success'):
            result['refresh_token'] = refresh_token
        return result
        
    except Exception as e:
        return {"error": str(e)}

# ============= API =============

@app.route('/')
def home():
    return send_file('panel.html')

@app.route('/api/fetch', methods=['POST'])
def fetch_emails():
    data = request.json
    credential = data.get('credential', '').strip()
    
    if not credential:
        return jsonify({'error': 'ক্রেডেনশিয়াল দিন'})
    
    # ক্রেডেনশিয়াল পার্স
    parsed = parse_credential(credential)
    
    if not parsed:
        return jsonify({'error': 'ভুল ফরম্যাট। ব্যবহার করুন: email:password অথবা email:password:access_token:refresh_token'})
    
    email = parsed['email']
    password = parsed['password']
    access_token = parsed['access_token']
    refresh_token = parsed['refresh_token']
    
    # ১. প্রথমে access_token ব্যবহার করে চেষ্টা করি
    if access_token:
        result = fetch_emails_with_token(email, access_token)
        if result.get('success'):
            return jsonify(result)
        
        # টোকেন কাজ না করলে রিফ্রেশ চেষ্টা
        if refresh_token:
            new_token = refresh_access_token(refresh_token)
            if new_token:
                result = fetch_emails_with_token(email, new_token)
                if result.get('success'):
                    result['new_access_token'] = new_token
                    return jsonify(result)
    
    # ২. পাসওয়ার্ড থাকলে পাসওয়ার্ড দিয়ে লগইন
    if password:
        return jsonify(login_with_password(email, password))
    
    return jsonify({'error': 'লগইন করার কোন উপায় নেই। পাসওয়ার্ড বা টোকেন দিন।'})

# ============= সার্ভার রান =============
if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║   📧 Email OTP Reader - Credential String Support      ║
    ║   Server running at: http://localhost:5000             ║
    ║                                                         ║
    ║   📝 ফরম্যাট:                                           ║
    ║   email:password                                        ║
    ║   email:password:access_token:refresh_token             ║
    ║                                                         ║
    ║   ⚠️  শুধুমাত্র আপনার নিজের অ্যাকাউন্ট               ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0.0', port=5000)
