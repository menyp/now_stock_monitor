import yfinance as yf
import schedule
import time
import json
import os
from datetime import datetime, timedelta
import subprocess
import sys
import threading
from flask import Flask, jsonify, render_template_string

DATA_FILE = 'sn_monthly_data.json'
TICKER = 'NOW'


def get_current_month():
    now = datetime.now()
    return now.strftime('%Y-%m')

def get_today():
    return datetime.now().strftime('%Y-%m-%d')

def fetch_sn_price():
    ticker = yf.Ticker(TICKER)
    data = ticker.history(period='1d', interval='1m')
    if data.empty:
        return None
    # Get the latest available close price
    return float(data['Close'][-1])

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

import logging
logging.basicConfig(filename='sn_alerts.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def send_email_alert(subject, body, to_email):
    import smtplib
    from email.mime.text import MIMEText

    # ---- CONFIGURE THESE ----
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "menypeled@gmail.com"         # <-- Replace with your Gmail address
    sender_password = "upmjrmpzuthbbfpd"         # <-- Replace with your Gmail App Password
    # -------------------------

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [to_email], msg.as_string())
        print("[ALERT] Email sent!")
        logging.info("[ALERT] Email sent!")
    except Exception as e:
        print(f"[ALERT] Email failed: {e}")
        logging.error(f"[ALERT] Email failed: {e}")

def get_simulation_note():
    return "\n\nNote: This is a simulation, not a real alert."

def notify_peak(price, is_simulation=False):
    message = f"SN stock hit a new monthly peak: ${price:.2f}"
    title = "ServiceNow Stock Alert"
    if is_simulation:
        message += get_simulation_note()
    print(f"[ALERT] Triggering alert: {message}")
    logging.info(f"[ALERT] Triggering alert: {message}")
    
    # Only run local notifications if not in cloud environment
    if os.environ.get('ENVIRONMENT') != 'production':
        # Try to play sound on macOS
        try:
            subprocess.Popen(['afplay', '/System/Library/Sounds/Glass.aiff'])
        except Exception:
            pass
            
        # Try to show Mac notification
        try:
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(['osascript', '-e', script], capture_output=True)
        except Exception as e:
            print(f"[ALERT] Local notification failed: {e}")
            logging.error(f"[ALERT] Local notification failed: {e}")
    
    # ---- SEND EMAIL ALERT ----
    try:
        send_email_alert(title, message, "menypeled@gmail.com")  # <-- Replace with your destination email
    except Exception as e:
        print(f"[ALERT] Email notification failed: {e}")
        logging.error(f"[ALERT] Email notification failed: {e}")

def monitor_stock():
    data = load_data()
    month = get_current_month()
    today = get_today()
    current_price = fetch_sn_price()
    if current_price is None:
        print("Could not fetch SN price.")
        return

    # Always recalculate baseline on every run/refresh
    ticker = yf.Ticker(TICKER)
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    hist = ticker.history(start=month_start, end=next_month, interval='1d')
    if not hist.empty:
        first_market_day = hist.index[0]
        minute_hist = ticker.history(start=first_market_day, end=first_market_day + timedelta(days=1), interval='1m')
        if not minute_hist.empty:
            first_minute_row = minute_hist.iloc[0]
            baseline_price = float(first_minute_row['Open'])
            baseline_date = first_minute_row.name.strftime('%Y-%m-%d %H:%M')
        else:
            first_open_row = hist.iloc[0]
            baseline_price = float(first_open_row['Open'])
            baseline_date = first_open_row.name.strftime('%Y-%m-%d')
    else:
        baseline_price = current_price
        baseline_date = today

    if month not in data:
        # First run this month: set only baseline and current price; leave peak unset
        data[month] = {
            'baseline_date': baseline_date,
            'baseline_price': baseline_price,
            'peak_price': None,
            'peak_date': None,
            'current_price': current_price,
            'peak_simulated': False,
            'last_real_peak_price': None,
            'last_real_peak_date': None,
        }
        save_data(data)
        print(f"Initialized baseline for {month}: ${baseline_price:.2f} on {baseline_date}")
        return
    else:
        # Always update baseline to the correct value
        data[month]['baseline_date'] = baseline_date
        data[month]['baseline_price'] = baseline_price

    # Always update current price
    data[month]['current_price'] = current_price

    # If the peak was simulated, revert to last real peak
    if data[month].get('peak_simulated'):
        data[month]['peak_price'] = data[month].get('last_real_peak_price', data[month]['baseline_price'])
        data[month]['peak_date'] = data[month].get('last_real_peak_date', data[month]['baseline_date'])
        data[month]['peak_simulated'] = False
        save_data(data)
        print(f"Simulated peak cleared. Restored last real peak for {month}: {data[month]['peak_price']} on {data[month]['peak_date']}")

    # Check for new real peak (must be above both previous peak and baseline)
    last_real = data[month]['last_real_peak_price'] if data[month]['last_real_peak_price'] is not None else data[month]['baseline_price']
    if current_price > max(last_real, data[month]['baseline_price']):
        data[month]['peak_price'] = current_price
        data[month]['peak_date'] = today
        data[month]['last_real_peak_price'] = current_price
        data[month]['last_real_peak_date'] = today
        save_data(data)
        notify_peak(current_price)
        print(f"New monthly peak: ${current_price:.2f}")
    else:
        save_data(data)
        print(f"Checked: ${current_price:.2f} (Current peak: {data[month]['peak_price']})")

def start_scheduler():
    print("Starting SN stock monitor...")
    monitor_stock()  # Run once at start
    schedule.every(10).minutes.do(monitor_stock)
    while True:
        schedule.run_pending()
        time.sleep(10)

# --- Flask Web Interface ---
app = Flask(__name__)

@app.route('/')
def dashboard():
    html = '''
    <style>
    body { background: #f6f8fa; font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; }
    .container { max-width: 520px; margin: 40px auto; background: #fff; border-radius: 16px; box-shadow: 0 2px 16px #0002; padding: 32px 24px; text-align: center; }
    h2 { margin-top: 0; color: #2c3e50; font-size: 1.7em; letter-spacing: 0.5px; }
    h4 { margin: 12px 0 20px 0; font-weight: 400; color: #3b4b5a; }
    .fields-panel { display: flex; flex-direction: column; gap: 16px; margin: 18px 0 8px 0; }
    .field-card { display: flex; justify-content: space-between; align-items: center; background: #f9fbfc; border-radius: 8px; box-shadow: 0 1px 4px #0001; padding: 14px 18px; font-size: 1.13em; border: 1px solid #e3e7eb; }
    .field-label { color: #34495e; font-weight: 500; letter-spacing: 0.1px; }
    .field-value { color: #1976d2; font-weight: 600; font-size: 1.13em; letter-spacing: 0.1px; }
    .field-card.highlight { background: #e3fbe7; border: 1.5px solid #388e3c; }
    .field-card.highlight .field-value { color: #388e3c; font-weight: 700; font-size: 1.22em; }
    .field-card.big { font-size: 1.24em; padding: 20px 18px; }
    .field-card.two-cols .field-label { min-width: 55px; }
    .btn-group { display: flex; gap: 14px; justify-content: center; margin: 22px 0 14px 0; }
    button { background: #1976d2; color: #fff; border: none; border-radius: 8px; padding: 12px 24px; font-size: 1.08em; font-weight: 500; cursor: pointer; transition: background 0.18s, box-shadow 0.18s; box-shadow: 0 1px 4px #1976d220; }
    button:hover, button:focus { background: #1565c0; outline: none; box-shadow: 0 2px 8px #1976d230; }
    #msg { text-align: center; margin-top: 12px; min-height: 28px; font-weight: 500; font-size: 1.08em; letter-spacing: 0.1px; }
    .spinner { display: inline-block; width: 22px; height: 22px; border: 3px solid #1976d2; border-radius: 50%; border-top: 3px solid #fff; animation: spin 1s linear infinite; margin-right: 8px; vertical-align: middle; }
    @keyframes spin { 100% { transform: rotate(360deg); } }
    @media (max-width: 600px) {
      .container { max-width: 99vw; padding: 10px 2px; }
      h2 { font-size: 1.1em; }
      h4 { font-size: 1em; }
      .fields-panel { gap: 9px; }
      .field-card { padding: 8px 8px; font-size: 0.98em; }
      .field-label, .field-value { font-size: 0.98em; }
      button { padding: 8px 10px; font-size: 0.98em; }
    }
    </style>
    <div class="container">
      <h2>ServiceNow (NOW) Stock Monitor</h2>
      <h4>Month: <span id="month"></span></h4>
      <div class="fields-panel">
        <div class="field-card highlight big">
          <div class="field-label">Current Price</div>
          <div class="field-value" id="current_price">-</div>
        </div>
        <div class="field-card two-cols">
          <div class="field-label">Baseline</div>
          <div class="field-value" style="display:flex;gap:16px;justify-content:flex-end;width:100%;">
            <span id="baseline_price">-</span>
            <span style="color:#888;font-size:0.97em;">(<span id="baseline_date">-</span>)</span>
          </div>
        </div>
        <div class="field-card two-cols">
          <div class="field-label">Peak</div>
          <div class="field-value" style="display:flex;gap:16px;justify-content:flex-end;width:100%;">
            <span id="peak_price">-</span>
            <span style="color:#888;font-size:0.97em;">(<span id="peak_date">-</span>)</span>
          </div>
        </div>
      </div>
      <div class="btn-group">
        <button onclick="refreshStatus()">Refresh</button>
        <button onclick="simulatePeak()">Simulate Peak</button>
        <button onclick="clearAll()" style="background:#b71c1c;">Clear</button>
        <button onclick="testSound()" style="background:#4caf50;">Test Sound</button>
      </div>
      <div id="msg"></div>
    </div>
    <script>
    // Function to play notification sound in the browser
    function playNotificationSound() {
        // Create audio element with a simple beep sound (data URL for a short beep)
        const audio = new Audio("data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBwQxEEIFmcyO7c0q6FTgcAAEi10vvq28CXWAkAC1es6/r74spUCgAARa3z/vvixlEIAEGq8/7+5slTCQBCqvL+/ObJUgkAQarx/v3mx1IKAD+q8v7+58lSCQA/qvH+/ebHUgoAP6rx/v3mx1IKAD+p8f795sdSCgA+qfH+/ebHUgoAPqnx/v3mx1IKAD6p8f795sdSCgA+qfH+/ebHUgoAPqnx/v3mx1IKAD6p8f795sdSCgA+qfH+/ebHUgoAPqnx/v3mx1IKAD6p8f795sdSCgA+qfH+/ebHUgoAPqnx/v3mx1IKAD2p8f795sZSCgA9qfH+/ebGUgoAPanw/v3mxlIKAD2p8P795sZSCgA9qfD+/ebGUgoAPanw/v3mxlIKAD2p8P795sZSCgA9qfD+/ebGUgoAPanw/v3mxlIKAD2p8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA8qfD+/ebGUgoAPKnw/v3mxlIKADyp8P795sZSCgA7qfD+/ebGUgoAO6nw/v3mxlIKADup8P795sZSCgA7qfD+/ebGUgoAO6nw/v3mxlIKADup8P795sZSCgA7qfD+/ebGUgoAO6nw/v3mxlIKADup8P795sZSCgA7qfD+/ebGUgoAO6nw/v3mxlIKADup8P795sZSCgA7qfD+/ebGUgoAO6nw/v3mxlIKADup8P795sZSCgA7qfD+/ebGUgoAO6nw/v3mxlIKADuqPD+/ebGUgoAOqny/v3myFIKADup8v797shSCgA6qvP+/ejIUQsAOarz/v7pxlAMADmr9P7/6MRPDAA4rPb+/+bBTg4ANa/5/v/juUwRADLC/Pv55LJEFD4AAM3f8eq9ekAAADMWl9K8gVRQTnaCbAAajMNPUGn1/f1IPQAYmtclNl7iyO/sHAAAKMy/FClrk8PomRcAACLOyxIYZZrK8Z8TAAAhz9AJFGC14OKMEQAALdPIISRip9TkfxQAADfWxx0rZZrF6XgSAAA51dUcKnChtN5tEgAAQtPmGjE0U6b44E0MAABJ2dUfLS5zk9zVaxEAAEjbzB8qOHmPzddiEwAAS9LLJS08g4i7x2cXAABKy8wwKlFjeNDZYRYAAE7Py0guXEV9ycJxGQAATszQUCxoF5NAqxwAAFbMzWgrdodfVJAfAABJbVoNAAECAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMA==");
        audio.play();
        console.log("Notification sound played");
    }
    
    // Function to test the notification sound
    function testSound() {
        playNotificationSound();
        showMsg('Testing sound notification...', 'green');
        setTimeout(()=>{document.getElementById('msg').innerText='';}, 1800);
    }
    
    function updateTable(data) {
        document.getElementById('month').innerText = data.month || '-';
        document.getElementById('baseline_date').innerText = data.baseline_date || '-';
        document.getElementById('baseline_price').innerText = data.baseline_price || '-';
        document.getElementById('peak_price').innerText = (data.peak_price === undefined || data.peak_price === null) ? '–' : data.peak_price;
        document.getElementById('peak_date').innerText = (data.peak_date === undefined || data.peak_date === null) ? '–' : data.peak_date;
        document.getElementById('current_price').innerText = data.current_price || '-';
    }
    function clearAll() {
        showSpinner('Clearing...');
        fetch('/api/clear', {method:'POST'})
        .then(r=>r.json()).then(data=>{
            updateTable({});
            showMsg('All values cleared!', 'red');
        });
    }
    function clearTable() {
        document.getElementById('baseline_date').innerText = '';
        document.getElementById('baseline_price').innerText = '';
        document.getElementById('peak_date').innerText = '';
        document.getElementById('peak_price').innerText = '';
        document.getElementById('current_price').innerText = '';
        document.getElementById('month').innerText = '';
    }
    function showSpinner(msg) {
        document.getElementById('msg').innerHTML = '<span class="spinner"></span>' + msg;
    }
    function showMsg(msg, color) {
        document.getElementById('msg').innerHTML = '<span style="color:' + (color||'green') + '">' + msg + '</span>';
    }
    function refreshStatus() {
        clearTable();
        showSpinner('Refreshing...');
        fetch('/api/refresh', {method:'POST'})
        .then(r=>r.json()).then(data=>{
            updateTable(data.status);
            showMsg(data.message || 'Refreshed!', 'green');
            setTimeout(()=>{document.getElementById('msg').innerText='';}, 1800);
        }).catch(()=>{
            showMsg('Failed to refresh.', 'red');
        });
    }
    function simulatePeak() {
        showSpinner('Simulating...');
        fetch('/api/simulate_peak', {method:'POST'})
        .then(r=>r.json()).then(data=>{
            updateTable(data.status);
            showMsg(data.message || 'Simulated peak!', 'green');
            playNotificationSound(); // Play sound notification when a peak is simulated
            setTimeout(()=>{document.getElementById('msg').innerText='';}, 1800);
        }).catch(()=>{
            showMsg('Failed to simulate.', 'red');
        });
    }
    // Store the current peak value to detect changes
    let previousPeakValue = null;
    
    // Check if peak value has changed and notify if it has
    function checkForPeakChanges(data) {
        // First update the table with new data
        updateTable(data);
        
        // Check if this is a new peak
        if (data.peak_price !== null && 
            data.peak_price !== undefined &&
            previousPeakValue !== null &&
            previousPeakValue !== undefined &&
            data.peak_price > previousPeakValue) {
            
            // Play notification for new peak
            playNotificationSound();
            showMsg('New peak detected!', 'green');
            setTimeout(()=>{document.getElementById('msg').innerText='';}, 3000);
        }
        
        // Update our stored peak value
        previousPeakValue = data.peak_price;
    }
    
    // Initial load
    function loadStatus() {
        fetch('/api/status')
            .then(r => r.json())
            .then(data => {
                previousPeakValue = data.peak_price;
                updateTable(data);
            });
    }
    
    // Set up automatic polling to check for changes
    function startAutomaticChecking() {
        // Check every 10 seconds for updates
        setInterval(() => {
            fetch('/api/status')
                .then(r => r.json())
                .then(checkForPeakChanges);
        }, 10000); // 10 seconds
    }
    
    // Initialize everything
    loadStatus();
    startAutomaticChecking();
    </script>
    '''
    return render_template_string(html)

@app.route('/api/status')
def api_status():
    data = load_data()
    month = get_current_month()
    month_data = data.get(month, {})
    return jsonify({"month": month, **month_data})

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    monitor_stock()  # Force a check
    data = load_data()
    month = get_current_month()
    month_data = data.get(month, {})
    return jsonify({"status": {"month": month, **month_data}, "message": "Refreshed!"})

@app.route('/api/clear', methods=['POST'])
def api_clear():
    data = load_data()
    month = get_current_month()
    if month in data:
        del data[month]
        save_data(data)
    return jsonify({'status': {}, 'message': 'Cleared!'})

@app.route('/api/simulate_peak', methods=['POST'])
def api_simulate_peak():
    # Simulate a new peak by incrementing last real peak by 100 and triggering notify_peak
    data = load_data()
    month = get_current_month()
    if month not in data:
        return jsonify({"status": {"month": month}, "message": "No data for this month."})
    last_real_peak = data[month]['last_real_peak_price'] if data[month]['last_real_peak_price'] is not None else data[month]['baseline_price']
    simulated_peak = last_real_peak + 100
    data[month]['current_price'] = simulated_peak
    data[month]['peak_price'] = simulated_peak
    data[month]['peak_date'] = get_today()
    data[month]['peak_simulated'] = True
    save_data(data)
    notify_peak(simulated_peak, is_simulation=True)
    return jsonify({"status": {"month": month, **data[month]}, "message": "Simulated peak!"})

if __name__ == '__main__':
    # Get port from environment variable for cloud deployment
    port = int(os.environ.get('PORT', 5001))
    
    # Only send email if not in production (to avoid spamming)
    if os.environ.get('ENVIRONMENT') != 'production':
        try:
            send_email_alert(
                "SN Stock Monitor Started",
                f"The SN stock monitor script has started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.",
                "menypeled@gmail.com"
            )
        except Exception as e:
            print(f"Email notification failed: {e}")
    
    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Start the Flask web server - bind to 0.0.0.0 for cloud deployment
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'True').lower() == 'true')
