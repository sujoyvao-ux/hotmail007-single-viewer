from flask import Flask, request, jsonify, send_file, redirect, session
from flask_cors import CORS
import requests
import re
import json
import urllib.parse
import secrets
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app)

# ============= আপনার Azure অ্যাপের তথ্য =============
# 🔴 এখানে আপনার নিজের তথ্য দিন
CLIENT_ID = "YOUR_CLIENT_ID_HERE"        # Azure Portal থেকে Client ID
CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE" # Azure Portal থেকে Client Secret
REDIRECT_URI = "http://localhost:5000/auth/callback"
AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = "Mail.Read User.Read offline_access"

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
def fetch_emails_with_token(access_token):
    try:
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        
        # ইউজার ইনফো
        user_res = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        if user_res.status_code != 200:
            return {"error": f"টোকেন বৈধ নয় (Status: {user_res.status_code})"}
        
        user_data = user_res.json()
        user_name = user_data.get("displayName") or user_data.get("userPrincipalName", "Unknown")
        email = user_data.get("userPrincipalName") or user_data.get("mail", "Unknown")
        
        # ইমেইল ফেচ
        url = "https://graph.microsoft.com/v1.0/me/mailfolders/inbox/messages"
        params = {
            "$top": 20,
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
                'preview': preview[:300] if preview else '',
                'received': received,
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

# ============= অথোরাইজেশন URL =============
@app.route('/auth/login')
def auth_login():
    state = secrets.token_hex(16)
    session['state'] = state
    
    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPES,
        'response_mode': 'query',
        'state': state
    }
    auth_url = f"{AUTHORITY}/oauth2/v2.0/authorize?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)

# ============= কলব্যাক =============
@app.route('/auth/callback')
def auth_callback():
    code = request.args.get('code')
    error = request.args.get('error')
    state = request.args.get('state')
    
    if error:
        return f"""
        <html>
            <head><style>body{{font-family:Arial;padding:40px;background:#0a0a1a;color:#fff;text-align:center;}}</style></head>
            <body>
                <h2>❌ Error: {error}</h2>
                <p style="color:#94a3b8;">লগইন ব্যর্থ হয়েছে</p>
                <a href="/" style="color:#7c3aed;">🔙 ফিরে যান</a>
            </body>
        </html>
        """
    
    if not code:
        return """
        <html>
            <head><style>body{{font-family:Arial;padding:40px;background:#0a0a1a;color:#fff;text-align:center;}}</style></head>
            <body>
                <h2>❌ কোন কোড পাওয়া যায়নি</h2>
                <a href="/" style="color:#7c3aed;">🔙 ফিরে যান</a>
            </body>
        </html>
        """
    
    try:
        # টোকেন নেওয়া
        token_url = f"{AUTHORITY}/oauth2/v2.0/token"
        token_data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        
        token_res = requests.post(token_url, data=token_data)
        
        if token_res.status_code != 200:
            return f"""
            <html>
                <head><style>body{{font-family:Arial;padding:40px;background:#0a0a1a;color:#fff;text-align:center;}}</style></head>
                <body>
                    <h2>❌ টোকেন Error</h2>
                    <p style="color:#f87171;">{token_res.text[:200]}</p>
                    <a href="/" style="color:#7c3aed;">🔙 ফিরে যান</a>
                </body>
            </html>
            """
        
        token_json = token_res.json()
        access_token = token_json.get('access_token')
        
        # ইমেইল ফেচ
        result = fetch_emails_with_token(access_token)
        
        if result.get('success'):
            return render_results(result)
        
        return f"""
        <html>
            <head><style>body{{font-family:Arial;padding:40px;background:#0a0a1a;color:#fff;text-align:center;}}</style></head>
            <body>
                <h2>❌ {result.get('error', 'অজানা Error')}</h2>
                <a href="/" style="color:#7c3aed;">🔙 ফিরে যান</a>
            </body>
        </html>
        """
        
    except Exception as e:
        return f"""
        <html>
            <head><style>body{{font-family:Arial;padding:40px;background:#0a0a1a;color:#fff;text-align:center;}}</style></head>
            <body>
                <h2>❌ Exception: {str(e)}</h2>
                <a href="/" style="color:#7c3aed;">🔙 ফিরে যান</a>
            </body>
        </html>
        """

def render_results(result):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>📧 Email OTP Reader - Results</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0a0a1a;
                color: #fff;
                min-height: 100vh;
                padding: 20px;
            }
            .container { max-width: 900px; margin: 0 auto; }
            .header {
                background: linear-gradient(135deg, #1a1a3e, #2d1b69);
                padding: 25px;
                border-radius: 16px;
                margin-bottom: 20px;
                text-align: center;
                border: 1px solid rgba(255,255,255,0.08);
            }
            .header h1 {
                font-size: 2rem;
                background: linear-gradient(90deg, #00d2ff, #a855f7);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .card {
                background: rgba(255,255,255,0.04);
                border-radius: 14px;
                padding: 20px;
                margin-bottom: 15px;
                border: 1px solid rgba(255,255,255,0.06);
            }
            .user-info {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 10px;
                padding: 12px 16px;
                background: rgba(168, 85, 247, 0.08);
                border-radius: 10px;
                border: 1px solid rgba(168, 85, 247, 0.1);
            }
            .user-name { color: #c084fc; font-weight: 600; }
            .user-email { color: #94a3b8; }
            .success { color: #34d399; font-weight: 600; }
            .email-item {
                background: rgba(255,255,255,0.03);
                padding: 14px 18px;
                margin: 8px 0;
                border-radius: 10px;
                border-left: 3px solid #7c3aed;
            }
            .email-item:hover {
                background: rgba(255,255,255,0.06);
            }
            .from { color: #60a5fa; font-weight: 600; }
            .subject { color: #e2e8f0; margin: 4px 0; }
            .time { color: #64748b; font-size: 0.8rem; }
            .otp-box {
                background: rgba(168, 85, 247, 0.15);
                color: #c084fc;
                font-size: 1.5rem;
                font-weight: 700;
                padding: 2px 16px;
                border-radius: 8px;
                display: inline-block;
                letter-spacing: 3px;
                border: 1px solid rgba(168, 85, 247, 0.2);
            }
            .no-otp { color: #64748b; }
            .preview {
                color: #94a3b8;
                font-size: 0.85rem;
                margin-top: 6px;
                padding: 8px 12px;
                background: rgba(0,0,0,0.2);
                border-radius: 6px;
                display: none;
            }
            .preview.show { display: block; }
            .toggle-preview {
                color: #7c3aed;
                cursor: pointer;
                font-size: 0.8rem;
                margin-top: 4px;
                display: inline-block;
            }
            .toggle-preview:hover { text-decoration: underline; }
            .btn {
                padding: 10px 24px;
                border: none;
                border-radius: 8px;
                font-size: 0.95rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                display: inline-block;
                text-decoration: none;
                text-align: center;
            }
            .btn-primary {
                background: linear-gradient(135deg, #7c3aed, #a855f7);
                color: #fff;
            }
            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(168, 85, 247, 0.3);
            }
            .btn-outline {
                background: transparent;
                color: #94a3b8;
                border: 1px solid rgba(255,255,255,0.1);
            }
            .btn-outline:hover {
                background: rgba(255,255,255,0.05);
                border-color: #7c3aed;
                color: #fff;
            }
            .footer {
                text-align: center;
                color: #475569;
                font-size: 0.8rem;
                padding: 20px 0;
                margin-top: 20px;
                border-top: 1px solid rgba(255,255,255,0.05);
            }
            .stats {
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
                margin: 10px 0;
            }
            .stat-item {
                background: rgba(255,255,255,0.04);
                padding: 8px 16px;
                border-radius: 8px;
                font-size: 0.9rem;
            }
            .stat-item .num { color: #c084fc; font-weight: 700; font-size: 1.2rem; }
            @media (max-width: 640px) {
                .header h1 { font-size: 1.5rem; }
                .user-info { flex-direction: column; text-align: center; }
                .stats { justify-content: center; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📧 Email OTP Reader</h1>
                <p style="color:#94a3b8;">ইমেইল থেকে OTP কোড সংগ্রহ করা হয়েছে</p>
            </div>
            
            <div class="card">
                <div class="user-info">
                    <span class="user-name">👤 {user}</span>
                    <span class="user-email">📧 {email}</span>
                    <span class="success">✅ {total}টি ইমেইল</span>
                </div>
                
                <div class="stats">
                    <div class="stat-item">📊 মোট ইমেইল: <span class="num">{total}</span></div>
                    <div class="stat-item">🔑 OTP পাওয়া: <span class="num">{otp_count}</span></div>
                </div>
            </div>
    """.format(
        user=result.get('user', 'Unknown'),
        email=result.get('email', 'Unknown'),
        total=result.get('total', 0),
        otp_count=sum(1 for e in result.get('emails', []) if e.get('has_otp'))
    )
    
    for idx, email in enumerate(result.get('emails', [])):
        if email.get('has_otp'):
            otp_display = f'<span class="otp-box">{email["otp"]}</span>'
        else:
            otp_display = '<span class="no-otp">🔴 OTP খুঁজে পাওয়া যায়নি</span>'
        
        html += f"""
            <div class="email-item">
                <div class="from">📤 {email.get('from', 'Unknown')}</div>
                <div class="subject">📌 {email.get('subject', 'No Subject')}</div>
                <div style="margin:8px 0;">{otp_display}</div>
                <div class="time">🕐 {email.get('received', '')[:19]}</div>
                <span class="toggle-preview" onclick="togglePreview({idx})">👁️ প্রিভিউ দেখুন</span>
                <div class="preview" id="preview-{idx}">{email.get('preview', 'কোনো প্রিভিউ নেই')}</div>
            </div>
        """
    
    html += """
            <div class="card" style="text-align:center;margin-top:15px;">
                <a href="/" class="btn btn-primary">🔄 আবার চেষ্টা করুন</a>
                <a href="/auth/login" class="btn btn-outline" style="margin-left:10px;">🔑 অন্য অ্যাকাউন্ট</a>
            </div>
            
            <div class="footer">
                ⚡ Microsoft Graph API ব্যবহার করে | আপনার নিজের ডেটা নিরাপদে রাখুন
            </div>
        </div>
        
        <script>
            function togglePreview(idx) {
                const el = document.getElementById('preview-' + idx);
                if (el) {
                    el.classList.toggle('show');
                }
            }
        </script>
    </body>
    </html>
    """
    return html

# ============= হোম পেজ =============
@app.route('/')
def home():
    return send_file('panel.html')

# ============= API (ক্রেডেনশিয়াল স্ট্রিং দিয়ে) =============
@app.route('/api/fetch', methods=['POST'])
def fetch_emails_api():
    data = request.json
    credential = data.get('credential', '').strip()
    
    if not credential:
        return jsonify({'error': 'ক্রেডেনশিয়াল দিন'})
    
    # ক্রেডেনশিয়াল পার্স
    parts = credential.split(':')
    access_token = None
    
    if len(parts) >= 4:
        # email:password:access_token:refresh_token
        access_token = parts[2]
    elif len(parts) == 3:
        # email:password:access_token
        access_token = parts[2]
    
    # টোকেন থাকলে ব্যবহার করি
    if access_token:
        result = fetch_emails_with_token(access_token)
        if result.get('success'):
            return jsonify(result)
    
    # টোকেন না থাকলে বা কাজ না করলে লগইন পেজে পাঠাই
    return jsonify({
        'error': 'টোকেন কাজ করছে না। লগইন পেজে যান: /auth/login',
        'login_url': '/auth/login'
    })

# ============= সার্ভার রান =============
if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║   📧 Email OTP Reader - Azure App Method                       ║
    ║   Server running at: http://localhost:5000                    ║
    ║                                                                 ║
    ║   ⚠️  আপনার CLIENT_ID এবং CLIENT_SECRET সেট করুন            ║
    ║                                                                 ║
    ║   🚀 ২টি উপায়:                                                 ║
    ║   1. /auth/login → ব্রাউজারে লগইন করুন                       ║
    ║   2. API → টোকেন দিয়ে ইমেইল ফেচ করুন                       ║
    ║                                                                 ║
    ║   📝 Azure App রেজিস্টার করতে ভুলবেন না!                      ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, host='0.0.0.0', port=5000)
