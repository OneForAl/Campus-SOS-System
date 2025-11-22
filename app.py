from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import logging

app = Flask(__name__)
app.secret_key = 'hackathon_secure_key'

# Configure logging to see alerts in the terminal
logging.basicConfig(level=logging.INFO)

# --- MOCK DATABASE ---
# In a real production app, use SQLite or PostgreSQL.
# For the hackathon, a list of dictionaries is faster and sufficient.
alerts = []

@app.route('/')
def index():
    """Student View: The SOS Button"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Admin View: The Map"""
    # Simple auth check
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Simple Login for Security Guards"""
    if request.method == 'POST':
        if request.form.get('password') == 'admin123':
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('index.html', error="Invalid Password") # Quick hack to show error
    return render_template('index.html', login_mode=True)

# --- API ENDPOINTS ---

@app.route('/api/alert', methods=['POST'])
def receive_alert():
    """
    RECEIVER: Android App & Web Client send data here.
    Expected JSON: { "lat": float, "long": float, "student_id": str, "source": str }
    """
    data = request.json
    
    if not data:
        return jsonify({"status": "error", "message": "No JSON data received"}), 400

    new_alert = {
        "id": len(alerts) + 1,
        "lat": data.get('lat'),
        "long": data.get('long'),
        "student_id": data.get('student_id', 'Unknown'),
        "source": data.get('source', 'WEB'), # 'ANDROID' or 'WEB'
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "status": "Active"
    }

    alerts.append(new_alert)
    logging.info(f"🚨 ALERT RECEIVED: {new_alert}")
    
    return jsonify({"status": "success", "alert_id": new_alert['id']}), 200

@app.route('/api/get_alerts', methods=['GET'])
def get_alerts():
    """
    PROVIDER: The Dashboard calls this every 2 seconds to check for new alerts.
    """
    return jsonify(alerts)

if __name__ == '__main__':
    # host='0.0.0.0' allows external devices (like the Android phone) to connect
    app.run(debug=True, host='0.0.0.0', port=5000)