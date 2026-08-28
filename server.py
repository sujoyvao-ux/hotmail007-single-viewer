from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import requests
import re
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ============= কনফিগারেশন =============
API_KEY = os.environ.get('API_KEY', '')
BASE_URL = os.environ.get('BASE_URL', 'https://gapi.hotmail007.com')

# ============= OTP খোঁজার ফাংশন =============
def find_otp(text):
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
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).replace(' ', '').replace('-', '')
    return None

# ============= ইমেইল ফেচ (একাধিক) =============
@app.route('/api/fetch', methods=['POST'])
def fetch_emails():
    data = request.json
    account = data.get('account', '').strip()
    limit = data.get('limit', 5)
    folder = data.get('folder', 'inbox')
    
    if not account:
        return jsonify({'error': 'অ্যাকাউন্ট দিন', 'success': False})
    
    if not API_KEY:
        return jsonify({'error': 'API_KEY সেট করুন', 'success': False})
    
    emails = []
    params = {
        'clientKey': API_KEY,
        'account': account,
        'folder': folder
    }
    
    try:
        for i in range(min(limit, 10)):
            url = f"{BASE_URL}/open/mail/latest"
            response = requests.get(url, params=params, timeout=30)
            result = response.json()
            
            if result.get('success') and result.get('data'):
                email = result['data']
                full_text = email.get('subject', '') + " " + email.get('text', '') + " " + email.get('html', '')
                otp = find_otp(full_text)
                
                # সময় ফরম্যাট
                received = email.get('receivedAt', '')
                try:
                    dt = datetime.fromisoformat(received.replace('Z', '+00:00'))
                    received = dt.strftime('%d %b %Y, %I:%M %p')
                except:
                    pass
                
                emails.append({
                    'from': email.get('from', 'Unknown'),
                    'subject': email.get('subject', 'No Subject'),
                    'text': email.get('text', '')[:300],
                    'html': email.get('html', ''),
                    'receivedAt': received,
                    'otp': otp if otp else None,
                    'has_otp': otp is not None
                })
                
                # পরবর্তী ইমেইলের জন্য timestamp আপডেট
                if email.get('receivedAt'):
                    try:
                        dt = datetime.fromisoformat(email['receivedAt'].replace('Z', '+00:00'))
                        params['start_timestamp'] = int(dt.timestamp())
                    except:
                        pass
            else:
                break
        
        account_email = account.split(':')[0] if ':' in account else account
        
        return jsonify({
            'success': True,
            'total': len(emails),
            'account': account_email,
            'emails': emails
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'success': False})

# ============= ব্যালেন্স =============
@app.route('/api/balance')
def get_balance():
    if not API_KEY:
        return jsonify({'error': 'API_KEY সেট করুন', 'success': False})
    try:
        url = f"{BASE_URL}/open/balance"
        params = {'clientKey': API_KEY}
        response = requests.get(url, params=params, timeout=30)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e), 'success': False})

# ============= স্টক =============
@app.route('/api/stock')
def get_stock():
    product_id = request.args.get('productId')
    params = {}
    if product_id:
        params['productId'] = product_id
    try:
        url = f"{BASE_URL}/open/stock"
        response = requests.get(url, params=params, timeout=30)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e), 'success': False})

# ============= হোম পেজ =============
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

# ============= হেলথ চেক =============
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'api_key_set': bool(API_KEY)})

# ============= HTML টেমপ্লেট =============
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📧 Email OTP Reader</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a1a;
            color: #fff;
            min-height: 100vh;
            padding: 16px;
        }
        .container { max-width: 900px; margin: 0 auto; }
        
        /* Header */
        .header {
            background: linear-gradient(135deg, #1a1a3e, #2d1b69);
            padding: 24px 28px;
            border-radius: 16px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.08);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }
        .header h1 {
            font-size: 1.6rem;
            background: linear-gradient(90deg, #00d2ff, #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header p { color: #94a3b8; font-size: 0.85rem; margin-top: 2px; }
        .badge {
            display: inline-block;
            background: rgba(168,85,247,0.2);
            color: #a855f7;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 0.75rem;
            border: 1px solid rgba(168,85,247,0.2);
        }
        
        /* Cards */
        .card {
            background: rgba(255,255,255,0.04);
            border-radius: 14px;
            padding: 18px 20px;
            margin-bottom: 14px;
            border: 1px solid rgba(255,255,255,0.06);
        }
        .card-title {
            color: #e2e8f0;
            font-size: 0.95rem;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }
        .card-title small {
            color: #64748b;
            font-size: 0.75rem;
            font-weight: normal;
        }
        
        /* Balance */
        .balance-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 12px;
            padding: 10px 14px;
            background: rgba(168,85,247,0.06);
            border-radius: 10px;
            border: 1px solid rgba(168,85,247,0.08);
        }
        .balance-item .label { color: #64748b; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.5px; }
        .balance-item .value { color: #c084fc; font-size: 1.2rem; font-weight: 700; }
        .balance-item .value.green { color: #34d399; }
        .balance-item .value.gold { color: #fbbf24; }
        
        /* Inputs */
        textarea {
            width: 100%;
            min-height: 70px;
            padding: 10px 12px;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.05);
            color: #e2e8f0;
            font-size: 0.8rem;
            font-family: 'Courier New', monospace;
            resize: vertical;
            transition: all 0.3s ease;
            line-height: 1.5;
        }
        textarea:focus {
            outline: none;
            border-color: #a855f7;
            box-shadow: 0 0 20px rgba(168,85,247,0.1);
        }
        textarea::placeholder { color: #475569; }
        
        select, input[type="number"] {
            padding: 8px 12px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.05);
            color: #e2e8f0;
            font-size: 0.85rem;
            transition: all 0.3s ease;
            width: 100%;
        }
        select:focus, input:focus {
            outline: none;
            border-color: #a855f7;
        }
        select option { background: #1a1a2e; color: #fff; }
        
        .flex { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
        .flex-1 { flex: 1; min-width: 120px; }
        .mt-10 { margin-top: 10px; }
        .mb-10 { margin-bottom: 10px; }
        .gap-8 { gap: 8px; }
        
        /* Buttons */
        .btn {
            padding: 10px 22px;
            border: none;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            justify-content: center;
        }
        .btn-primary {
            background: linear-gradient(135deg, #7c3aed, #a855f7);
            color: #fff;
        }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(168,85,247,0.3); }
        .btn-success {
            background: linear-gradient(135deg, #059669, #10b981);
            color: #fff;
        }
        .btn-success:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(16,185,129,0.3); }
        .btn-outline {
            background: transparent;
            color: #94a3b8;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .btn-outline:hover { background: rgba(255,255,255,0.05); border-color: #7c3aed; color: #fff; }
        .btn-sm { padding: 6px 14px; font-size: 0.78rem; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; }
        .btn-block { width: 100%; }
        
        /* Status */
        .status {
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.85rem;
            margin-top: 8px;
            display: none;
        }
        .status.show { display: block; }
        .status.success { background: rgba(52,211,153,0.1); color: #34d399; border: 1px solid rgba(52,211,153,0.1); }
        .status.error { background: rgba(248,113,113,0.1); color: #f87171; border: 1px solid rgba(248,113,113,0.1); }
        .status.loading { background: rgba(96,165,250,0.1); color: #60a5fa; border: 1px solid rgba(96,165,250,0.1); display: block; }
        .status.info { background: rgba(251,191,36,0.1); color: #fbbf24; border: 1px solid rgba(251,191,36,0.1); display: block; }
        
        /* User Info Bar */
        .user-bar {
            display: none;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
            padding: 10px 14px;
            background: rgba(168,85,247,0.08);
            border-radius: 8px;
            border: 1px solid rgba(168,85,247,0.1);
            margin-top: 10px;
        }
        .user-bar.show { display: flex; }
        .user-bar .email { color: #c084fc; font-weight: 600; }
        .user-bar .count { color: #34d399; }
        .user-bar .method { color: #fbbf24; font-size: 0.8rem; }
        
        /* Email Items */
        .email-item {
            background: rgba(255,255,255,0.03);
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 10px;
            border-left: 3px solid #7c3aed;
            transition: all 0.3s ease;
        }
        .email-item:hover { background: rgba(255,255,255,0.06); transform: translateX(4px); }
        .email-item .from { color: #60a5fa; font-weight: 600; font-size: 0.95rem; }
        .email-item .subject { color: #e2e8f0; margin: 4px 0; }
        .email-item .time { color: #64748b; font-size: 0.78rem; }
        .email-item .otp-box {
            background: rgba(168,85,247,0.15);
            color: #c084fc;
            font-size: 1.3rem;
            font-weight: 700;
            padding: 2px 14px;
            border-radius: 6px;
            display: inline-block;
            letter-spacing: 2px;
            border: 1px solid rgba(168,85,247,0.2);
            margin: 4px 0;
        }
        .email-item .preview {
            color: #94a3b8;
            font-size: 0.82rem;
            margin-top: 6px;
            padding: 8px 12px;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
            display: none;
            max-height: 120px;
            overflow-y: auto;
        }
        .email-item .preview.show { display: block; }
        .toggle-preview {
            color: #7c3aed;
            cursor: pointer;
            font-size: 0.78rem;
            margin-top: 4px;
            display: inline-block;
        }
        .toggle-preview:hover { text-decoration: underline; }
        
        /* Loading */
        .loading {
            text-align: center;
            padding: 30px;
            color: #94a3b8;
        }
        .loading .spinner {
            display: inline-block;
            width: 28px;
            height: 28px;
            border: 3px solid rgba(168,85,247,0.2);
            border-top-color: #a855f7;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .empty-state {
            text-align: center;
            padding: 35px;
            color: #64748b;
        }
        .empty-state .icon { font-size: 2.5rem; margin-bottom: 8px; }
        
        .footer {
            text-align: center;
            color: #475569;
            font-size: 0.75rem;
            padding: 16px 0;
            margin-top: 16px;
            border-top: 1px solid rgba(255,255,255,0.05);
        }
        
        /* Responsive */
        @media (max-width: 640px) {
            .header h1 { font-size: 1.3rem; }
            .header { padding: 16px 18px; }
            .card { padding: 14px 16px; }
            .balance-grid { grid-template-columns: repeat(2, 1fr); }
            .flex { flex-direction: column; }
            .flex-1 { width: 100%; }
            .btn { width: 100%; justify-content: center; }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div>
                <h1>📧 Email OTP Reader</h1>
                <p>ক্রেডেনশিয়াল পেস্ট করুন → OTP দেখুন</p>
            </div>
            <div>
                <span class="badge">🔒 নিজের অ্যাকাউন্ট</span>
                <span class="badge" style="margin-left:6px;">⚡ Real-time</span>
            </div>
        </div>

        <!-- Balance -->
        <div class="card">
            <div class="flex" style="justify-content:space-between;">
                <span class="card-title" style="margin-bottom:0;">💰 ব্যালেন্স</span>
                <button class="btn btn-outline btn-sm" onclick="loadBalance()">🔄</button>
            </div>
            <div class="balance-grid" id="balanceInfo">
                <div class="balance-item"><span class="label">ব্যালেন্স</span><span class="value" id="bal">—</span></div>
                <div class="balance-item"><span class="label">VIP</span><span class="value gold" id="vip">—</span></div>
                <div class="balance-item"><span class="label">ডিসকাউন্ট</span><span class="value green" id="discount">—</span></div>
            </div>
        </div>

        <!-- Main Input -->
        <div class="card">
            <div class="card-title">
                🔑 ক্রেডেনশিয়াল স্ট্রিং
                <small>(email:password:access_token:refresh_token)</small>
            </div>
            
            <textarea id="credInput" placeholder="আপনার ক্রেডেনশিয়াল পেস্ট করুন...">UnTempest26@outlook.com:0daJpj8haw1:M.C545_BL2.0.U.MsaArtifacts.-Chk68JvtmKMDe92LdyW9VB3Bc3imQ3pK2C573dCGi4TPwn1xU7rJxvIXxOdMVW!KD8PX4H6R!W3DVpcIbIAVVIoY05UOI7SKxtlJWL5O5qtSPFvSZ97F1v*K8RXROXDw1kpW7lBZKEKOutLMMVeexMDOWn2Ml5Cs3meAVnl0Y3qVKmXf3rtYyu8*uJ1zitlOISk5xP17ZMjs6sbQ5WGffEelf3FFnTMvKBVgCc0IzNlIBmidrvIiwq6C9fNgf0UecNNE9w1EjcMwqUuPfEIQ8ehs1s87Kyn3DYTx4BO8YQwREONK86BNhC*kyaduKM2hOxil837Ebrz7bmmlfxOzlPzd7nhRlvVbdIbKkpWicDYDe778IWY53NsK0qiO7r119ONQLjtYJMG5sjn7UaPxYFs$:8b4ba9dd-3ea5-4e5f-86f1-ddba2230dcf2</textarea>
            
            <div class="flex mt-10">
                <button class="btn btn-primary flex-1" onclick="fetchEmails()">🚀 ইমেইল দেখুন</button>
                <button class="btn btn-outline btn-sm" onclick="clearAll()">🗑️ ক্লিয়ার</button>
            </div>
            
            <div class="flex mt-10">
                <div class="flex-1">
                    <label style="color:#64748b;font-size:0.75rem;">📁 ফোল্ডার</label>
                    <select id="folderSelect">
                        <option value="inbox">📥 Inbox</option>
                        <option value="junkemail">📪 Junk</option>
                    </select>
                </div>
                <div class="flex-1">
                    <label style="color:#64748b;font-size:0.75rem;">📊 সংখ্যা</label>
                    <input type="number" id="limitInput" value="5" min="1" max="15">
                </div>
            </div>
            
            <div id="status" class="status"></div>
        </div>

        <!-- User Info -->
        <div class="user-bar" id="userBar">
            <span class="email" id="userEmail">📧</span>
            <span class="count" id="emailCount">0টি ইমেইল</span>
            <span class="method" id="apiMethod">🟢 API</span>
        </div>

        <!-- Results -->
        <div class="card" id="resultCard" style="display:none;padding:16px;">
            <div id="resultContainer">
                <div class="empty-state">
                    <div class="icon">📭</div>
                    <p>কোনো ইমেইল নেই</p>
                </div>
            </div>
        </div>

        <div class="footer">
            ⚡ Hotmail007 API | আপনার নিজের ডেটা নিরাপদে রাখুন
        </div>
    </div>

    <script>
        const credInput = document.getElementById('credInput');
        const statusEl = document.getElementById('status');
        const resultContainer = document.getElementById('resultContainer');
        const resultCard = document.getElementById('resultCard');
        const userBar = document.getElementById('userBar');
        const userEmail = document.getElementById('userEmail');
        const emailCount = document.getElementById('emailCount');
        const apiMethod = document.getElementById('apiMethod');
        const folderSelect = document.getElementById('folderSelect');
        const limitInput = document.getElementById('limitInput');

        // ============= ব্যালেন্স লোড =============
        async function loadBalance() {
            try {
                const res = await fetch('/api/balance');
                const data = await res.json();
                if (data.success && data.data) {
                    document.getElementById('bal').textContent = data.data.balance || '0';
                    document.getElementById('vip').textContent = data.data.vipName || `Lv${data.data.vipLevel || 0}`;
                    document.getElementById('discount').textContent = data.data.discountRate ? `${data.data.discountRate}%` : '—';
                }
            } catch(e) { console.log('Balance error:', e); }
        }

        // ============= ইমেইল ফেচ =============
        async function fetchEmails() {
            const account = credInput.value.trim();
            if (!account) {
                showStatus('⚠️ ক্রেডেনশিয়াল দিন', 'error');
                return;
            }

            const btn = document.querySelector('.btn-primary');
            btn.disabled = true;
            btn.innerHTML = '⏳ লোড...';
            
            showStatus('⏳ ইমেইল পড়া হচ্ছে...', 'loading');
            resultCard.style.display = 'none';
            userBar.classList.remove('show');

            try {
                const limit = parseInt(limitInput.value) || 5;
                const folder = folderSelect.value;
                
                const res = await fetch('/api/fetch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ account, limit, folder })
                });
                
                const data = await res.json();

                if (data.error) {
                    showStatus('❌ ' + data.error, 'error');
                    return;
                }

                if (data.success && data.emails) {
                    userBar.classList.add('show');
                    userEmail.textContent = '📧 ' + data.account;
                    emailCount.textContent = data.total + 'টি ইমেইল';
                    apiMethod.textContent = '🟢 API';

                    renderEmails(data.emails);
                    showStatus('✅ ' + data.total + 'টি ইমেইল পাওয়া গেছে', 'success');
                    resultCard.style.display = 'block';
                }
            } catch(e) {
                showStatus('❌ Error: ' + e.message, 'error');
            }

            btn.disabled = false;
            btn.innerHTML = '🚀 ইমেইল দেখুন';
        }

        // ============= ইমেইল রেন্ডার =============
        function renderEmails(emails) {
            if (!emails || emails.length === 0) {
                resultContainer.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">📭</div>
                        <p>কোনো ইমেইল নেই</p>
                    </div>
                `;
                return;
            }

            let html = '';
            emails.forEach((email, index) => {
                const otpDisplay = email.has_otp
                    ? `<div class="otp-box">🔑 ${email.otp}</div>`
                    : `<div style="color:#64748b;">🔴 OTP খুঁজে পাওয়া যায়নি</div>`;
                
                const textContent = email.text || email.html || '';
                
                html += `
                    <div class="email-item">
                        <div class="from">📤 ${escapeHtml(email.from)}</div>
                        <div class="subject">📌 ${escapeHtml(email.subject)}</div>
                        <div style="margin:6px 0;">${otpDisplay}</div>
                        <div class="time">🕐 ${escapeHtml(email.receivedAt || 'N/A')}</div>
                        <span class="toggle-preview" onclick="togglePreview(${index})">👁️ প্রিভিউ দেখুন</span>
                        <div class="preview" id="preview-${index}">${escapeHtml(textContent || 'কোনো কন্টেন্ট নেই')}</div>
                    </div>
                `;
            });
            resultContainer.innerHTML = html;
        }

        function togglePreview(index) {
            const el = document.getElementById('preview-' + index);
            if (el) el.classList.toggle('show');
        }

        function clearAll() {
            resultContainer.innerHTML = `
                <div class="empty-state">
                    <div class="icon">🗑️</div>
                    <p>ক্লিয়ার করা হয়েছে</p>
                </div>
            `;
            resultCard.style.display = 'none';
            userBar.classList.remove('show');
            showStatus('🗑️ ক্লিয়ার করা হয়েছে', 'info');
        }

        function showStatus(msg, type) {
            statusEl.textContent = msg;
            statusEl.className = 'status show ' + type;
        }

        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // ============= কীবোর্ড শর্টকাট =============
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.ctrlKey) {
                e.preventDefault();
                fetchEmails();
            }
        });

        // ============= পেজ লোড =============
        loadBalance();
        setTimeout(fetchEmails, 600);
    </script>
</body>
</html>
'''

# ============= সার্ভার রান =============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║   📧 Email OTP Reader - Updated Panel                          ║
    ║   Server running at: http://0.0.0.0:{port}                    ║
    ║                                                                 ║
    ║   🔑 API Key: {'✅ সেট আছে' if API_KEY else '❌ সেট নেই'}     ║
    ║   📡 Base URL: {BASE_URL}                                     ║
    ║                                                                 ║
    ║   ⚠️ শুধুমাত্র আপনার নিজের অ্যাকাউন্ট ব্যবহার করুন            ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=port)
