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

# ============= টোকেন দিয়ে ইমেইল ফেচ =============
def fetch_emails_with_token(access_token, limit=5):
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        user_res = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        if user_res.status_code != 200:
            return {
                "error": f"টোকেন বৈধ নয় (Status: {user_res.status_code})", 
                "status": user_res.status_code,
                "success": False
            }
        
        user_data = user_res.json()
        user_name = user_data.get("displayName") or user_data.get("userPrincipalName", "Unknown")
        email = user_data.get("userPrincipalName") or user_data.get("mail", "Unknown")
        
        url = "https://graph.microsoft.com/v1.0/me/mailfolders/inbox/messages"
        params = {
            "$top": limit,
            "$select": "subject,bodyPreview,from,receivedDateTime",
            "$orderby": "receivedDateTime desc"
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            return {
                "error": f"ইমেইল ফেচ করতে পারেনি (Status: {response.status_code})",
                "status": response.status_code,
                "success": False
            }
        
        emails = response.json().get("value", [])
        
        result = []
        for email_item in emails:
            subject = email_item.get('subject', '')
            preview = email_item.get('bodyPreview', '')
            from_addr = email_item.get('from', {}).get('emailAddress', {}).get('address', 'Unknown')
            received = email_item.get('receivedDateTime', '')
            
            full_text = subject + " " + preview
            otp = extract_otp(full_text)
            
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
        return {"error": str(e), "success": False}

# ============= Refresh Token দিয়ে নতুন টোকেন =============
def refresh_access_token(refresh_token):
    try:
        url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
        data = {
            "client_id": "00000000482c6b4a",
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        response = requests.post(url, data=data)
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'access_token': result.get('access_token'),
                'refresh_token': result.get('refresh_token')
            }
        return {'success': False, 'error': response.text}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============= পাসওয়ার্ড দিয়ে লগইন =============
def login_with_password(email, password):
    try:
        url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
        data = {
            "client_id": "00000000482c6b4a",
            "scope": "https://outlook.office.com/Mail.Read offline_access",
            "username": email,
            "password": password,
            "grant_type": "password"
        }
        response = requests.post(url, data=data)
        
        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'access_token': result.get('access_token'),
                'refresh_token': result.get('refresh_token')
            }
        return {'success': False, 'error': response.text}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============= ক্রেডেনশিয়াল পার্স =============
def parse_credential(cred_string):
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
    elif len(parts) == 2:
        return {
            'email': parts[0],
            'password': parts[1],
            'access_token': None,
            'refresh_token': None
        }
    else:
        return None

# ============= API - সম্পূর্ণ অটোমেটিক =============
@app.route('/api/fetch', methods=['POST'])
def fetch_emails_api():
    data = request.json
    credential = data.get('credential', '').strip()
    limit = data.get('limit', 5)
    
    if not credential:
        return jsonify({'error': 'ক্রেডেনশিয়াল দিন'})
    
    parsed = parse_credential(credential)
    if not parsed:
        return jsonify({'error': 'ভুল ফরম্যাট'})
    
    email = parsed.get('email')
    password = parsed.get('password')
    access_token = parsed.get('access_token')
    refresh_token = parsed.get('refresh_token')
    
    result = None
    new_credential = None
    
    # ===== STEP 1: access_token দিয়ে চেষ্টা =====
    if access_token:
        print("🔄 Trying with access_token...")
        result = fetch_emails_with_token(access_token, limit)
        if result.get('success'):
            print("✅ Access token worked!")
            return jsonify(result)
    
    # ===== STEP 2: refresh_token দিয়ে নতুন টোকেন =====
    if refresh_token and (not result or not result.get('success')):
        print("🔄 Trying refresh_token...")
        refresh_result = refresh_access_token(refresh_token)
        if refresh_result.get('success'):
            new_access = refresh_result.get('access_token')
            new_refresh = refresh_result.get('refresh_token')
            print("✅ New token obtained via refresh!")
            
            result = fetch_emails_with_token(new_access, limit)
            if result.get('success'):
                # নতুন ক্রেডেনশিয়াল তৈরি
                new_credential = f"{email}:{password}:{new_access}:{new_refresh}"
                result['new_credential'] = new_credential
                result['token_refreshed'] = True
                return jsonify(result)
    
    # ===== STEP 3: password দিয়ে লগইন =====
    if password and (not result or not result.get('success')):
        print("🔄 Trying login with password...")
        login_result = login_with_password(email, password)
        if login_result.get('success'):
            new_access = login_result.get('access_token')
            new_refresh = login_result.get('refresh_token')
            print("✅ Login successful!")
            
            result = fetch_emails_with_token(new_access, limit)
            if result.get('success'):
                new_credential = f"{email}:{password}:{new_access}:{new_refresh}"
                result['new_credential'] = new_credential
                result['token_refreshed'] = True
                return jsonify(result)
    
    # ===== সব ব্যর্থ =====
    if result and result.get('error'):
        return jsonify(result)
    
    return jsonify({'error': 'লগইন করার কোন উপায় নেই। চেক করুন আপনার ক্রেডেনশিয়াল সঠিক কিনা।'})

# ============= হোম পেজ =============
@app.route('/')
def home():
    return send_file('panel.html')

# ============= সার্ভার রান =============
if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║   📧 Email OTP Reader - সম্পূর্ণ অটোমেটিক                      ║
    ║   Server running at: http://localhost:5000                    ║
    ║                                                                 ║
    ║   🔄 অটোমেটিক যা যা হবে:                                       ║
    ║   1️⃣ access_token দিয়ে চেষ্টা                                ║
    ║   2️⃣ না হলে refresh_token দিয়ে নতুন টোকেন                   ║
    ║   3️⃣ না হলে password দিয়ে লগইন                              ║
    ║   4️⃣ নতুন টোকেন পেলে দেখাবে + নতুন ক্রেডেনশিয়াল দেবে       ║
    ║                                                                 ║
    ║   ⚠️ শুধুমাত্র আপনার নিজের অ্যাকাউন্ট ব্যবহার করুন            ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0.0', port=5000)
