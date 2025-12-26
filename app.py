import sqlite3
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import logging
import os

# NEW: Authlib for Google OAuth
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = 'hackathon_key'  # change to a strong secret in production
logging.basicConfig(level=logging.INFO)

# Database Name
DB_NAME = "campus_sos.db"

# --- GOOGLE OAUTH CONFIG ---
oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID', '962105562612-n82dut3lbjusnlpphfncqui5cotlp4cf.apps.googleusercontent.com'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
    # Add OIDC discovery so authlib can obtain jwks_uri automatically
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    api_base_url='https://openidconnect.googleapis.com/v1/',
    authorize_params={'prompt': 'select_account'},
    client_kwargs={
        'scope': 'openid email profile'
    }
)

ALLOWED_DOMAIN = "nitdelhi.ac.in"

# --- DATABASE SETUP ---
def init_db():
    """Creates the database table if it doesn't exist"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Create table for Alerts (add emergency_type)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            lat REAL,
            long REAL,
            source TEXT,
            timestamp TEXT,
            status TEXT,
            emergency_type TEXT
        )
    ''')
    conn.commit()

    # If upgrading from older DB without emergency_type, try to add column
    try:
        cursor.execute("ALTER TABLE alerts ADD COLUMN emergency_type TEXT")
        conn.commit()
    except Exception:
        # column already exists or cannot be added — ignore
        pass

    conn.close()

# Initialize DB immediately when app starts
init_db()

# --- HELPER TO CONNECT ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name (row['lat'])
    return conn

# --- LOGIN HELPERS ---
def current_user():
    return session.get('user')

def login_required(view_func):
    """Protect routes so only logged-in students (via Google) can access"""
    from functools import wraps

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for('student_login'))
        return view_func(*args, **kwargs)
    return wrapped

# --- ROUTES ---

@app.route('/')
@login_required
def index():
    # Only authenticated students see the SOS page
    user = current_user()
    return render_template('index.html', user=user)

@app.route('/dashboard')
def dashboard():
    # keep admin login logic as-is
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    user = session.get('user')  # pass student info (if any) to dashboard
    return render_template('dashboard.html', user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login (for security dashboard) – separate from student Google login"""
    if request.method == 'POST':
        # In a real app, use a hashed password!
        if request.form.get('password') == 'admin123':
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
    # Render the same index template but in admin login mode if you want
    return render_template('index.html', login_mode=True)

# ---------- STUDENT GOOGLE AUTH ----------

@app.route('/student/login')
def student_login():
    """Start Google OAuth flow for students"""
    redirect_uri = url_for('auth_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/callback')
def auth_callback():
    """Handle Google OAuth callback"""
    token = google.authorize_access_token()
    resp = google.get('userinfo')
    user_info = resp.json()

    email = user_info.get('email', '')
    name = user_info.get('name', 'Student')

    # Check domain
    if not email.endswith('@' + ALLOWED_DOMAIN):
        # Not from institute domain
        return "Access denied. Please use your institute email (@nitdelhi.ac.in).", 403

    # Save basic info in session
    session['user'] = {
        'email': email,
        'name': name,
    }
    logging.info(f"Student logged in: {email}")
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """Log out student"""
    session.pop('user', None)
    return redirect(url_for('student_login'))

# --- API ENDPOINTS ---

@app.route('/api/alert', methods=['POST'])
@login_required
def receive_alert():
    """Student must be logged in to send an alert"""
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400

    user = current_user()  # get email from session
    # Prepare data
    student_id = data.get('student_id') or user['email']
    lat = data.get('lat')
    long = data.get('long')
    source = data.get('source', 'WEB')
    emergency_type = data.get('emergency_type', 'Others')  # NEW: read dropdown
    timestamp = datetime.now().strftime("%H:%M:%S")
    status = "Active"

    # INSERT INTO DATABASE (include emergency_type)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO alerts (student_id, lat, long, source, timestamp, status, emergency_type) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (student_id, lat, long, source, timestamp, status, emergency_type)
    )
    conn.commit()
    new_id = cursor.lastrowid # Get the ID of the new row
    conn.close()

    print(f"✅ SAVED TO DB: ID {new_id} from {student_id} (type={emergency_type})")
    return jsonify({"status": "success", "id": new_id}), 200

@app.route('/api/get_alerts', methods=['GET'])
def get_alerts():
    # SELECT FROM DATABASE
    conn = get_db_connection()
    alerts = conn.execute('SELECT * FROM alerts ORDER BY id DESC').fetchall()
    conn.close()

    # Convert database rows to a list of dictionaries (JSON)
    alerts_list = []
    for row in alerts:
        alerts_list.append({
            "id": row['id'],
            "student_id": row['student_id'],
            "lat": row['lat'],
            "long": row['long'],
            "source": row['source'],
            "timestamp": row['timestamp'],
            "emergency_type": row['emergency_type'] if 'emergency_type' in row.keys() else 'Others'
        })

    return jsonify(alerts_list)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

