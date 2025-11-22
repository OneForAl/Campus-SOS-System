import sqlite3
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import logging

app = Flask(__name__)
app.secret_key = 'hackathon_key'
logging.basicConfig(level=logging.INFO)

# Database Name
DB_NAME = "campus_sos.db"

# --- DATABASE SETUP ---
def init_db():
    """Creates the database table if it doesn't exist"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Create table for Alerts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            lat REAL,
            long REAL,
            source TEXT,
            timestamp TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Initialize DB immediately when app starts
init_db()

# --- HELPER TO CONNECT ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name (row['lat'])
    return conn

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # In a real app, use a hashed password!
        if request.form.get('password') == 'admin123':
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
    return render_template('index.html', login_mode=True)

# --- API ENDPOINTS ---

@app.route('/api/alert', methods=['POST'])
def receive_alert():
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400

    # Prepare data
    student_id = data.get('student_id', 'Unknown')
    lat = data.get('lat')
    long = data.get('long')
    source = data.get('source', 'WEB')
    timestamp = datetime.now().strftime("%H:%M:%S")
    status = "Active"

    # INSERT INTO DATABASE
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO alerts (student_id, lat, long, source, timestamp, status) VALUES (?, ?, ?, ?, ?, ?)',
        (student_id, lat, long, source, timestamp, status)
    )
    conn.commit()
    new_id = cursor.lastrowid # Get the ID of the new row
    conn.close()

    print(f"✅ SAVED TO DB: ID {new_id} from {student_id}")
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
            "timestamp": row['timestamp']
        })

    return jsonify(alerts_list)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)