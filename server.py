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

# ============= Refresh Token দিয়ে নতুন Access Token =============
def refresh_access_token(refresh_token):
    """
    Refresh Token ব্যবহার করে নতুন Access Token তৈরি করে
    """
    try:
        url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
        
        data = {
            "client_id": "00000000482c6b4a",
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        response = requests.post(url, data=data, headers=headers)
        
        print(f"Refresh Token Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            new_access_token = result.get('access_token')
            new_refresh_token = result.get('refresh_token')
            
            if new_access_token:
                return {
                    'success': True,
                    'access_token': new_access_token,
                    'refresh_token': new_refresh_token or refresh_token
                }
            else:
                return {'success': False, 'error': 'No access token in response'}
        else:
            error_data = response.json()
            error_msg = error_data.get('error_description', 'Unknown error')
            return {'success': False, 'error': f'Refresh failed: {error_msg}'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============= টোকেন দিয়ে ইমেইল ফেচ =============
def fetch_emails_with_token(access_token, limit=5):
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        # ইউজার ইনফো
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
        
        # ইমেইল ফেচ
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

# ============= API - ইমেইল ফেচ (Refresh Token Support) =============
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
    email = parsed.get('email')
    
    if not access_token:
        return jsonify({'error': 'টোকেন পাওয়া যায়নি'})
    
    # প্রথমে access_token দিয়ে চেষ্টা
    result = fetch_emails_with_token(access_token, limit)
    
    # যদি 401 error আসে (টোকেন মেয়াদ শেষ)
    if not result.get('success') and result.get('status') == 401:
        print("🔄 Token expired, trying to refresh...")
        
        # refresh_token থাকলে নতুন টোকেন তৈরি করি
        if refresh_token:
            refresh_result = refresh_access_token(refresh_token)
            
            if refresh_result.get('success'):
                new_access_token = refresh_result.get('access_token')
                new_refresh_token = refresh_result.get('refresh_token')
                
                print("✅ New token obtained successfully!")
                
                # নতুন টোকেন দিয়ে আবার চেষ্টা
                result = fetch_emails_with_token(new_access_token, limit)
                
                if result.get('success'):
                    # নতুন টোকেন রিটার্ন করি
                    result['new_access_token'] = new_access_token
                    result['new_refresh_token'] = new_refresh_token
                    return jsonify(result)
                else:
                    return jsonify({
                        'error': f'নতুন টোকেন দিয়েও কাজ হয়নি: {result.get("error")}',
                        'needs_login': True
                    })
            else:
                return jsonify({
                    'error': f'Refresh Token কাজ করছে না: {refresh_result.get("error")}',
                    'needs_login': True
                })
        else:
            return jsonify({
                'error': 'টোকেন মেয়াদ শেষ হয়েছে এবং Refresh Token নেই',
                'needs_login': True
            })
    
    return jsonify(result)

# ============= হোম পেজ =============
@app.route('/')
def home():
    return send_file('panel.html')

# ============= সার্ভার রান =============
if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║   📧 Email OTP Reader - Auto Refresh Token Support         ║
    ║   Server running at: http://localhost:5000                 ║
    ║                                                             ║
    ║   🔄 Token মেয়াদ শেষ হলে Auto Refresh হবে!                ║
    ║   ⚠️ শুধুমাত্র আপনার নিজের অ্যাকাউন্ট ব্যবহার করুন        ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0.0', port=5000)
