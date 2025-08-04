import yfinance as yf
import schedule
import time
import json
import os
from datetime import datetime, timedelta
import subprocess
import sys
import threading
from flask import Flask, jsonify, render_template_string, request

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
            data = json.load(f)
            # Initialize email_recipients if not present
            if 'email_recipients' not in data:
                data['email_recipients'] = ["menypeled@gmail.com"]  # Default recipient
            return data
    # Return default empty data structure with email_recipients
    return {'email_recipients': ["menypeled@gmail.com"]}

def format_window_key(start_date, end_date):
    """Create a unique key for a trading window"""
    return f"{start_date}_to_{end_date}"

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
    message = f"SN stock hit a new monthly peak: ${price:.2f}\n\nFor more info visit the SN stock monitor: https://now-stock-monitor.onrender.com/"
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
    
    # ---- SEND EMAIL ALERTS TO ALL RECIPIENTS ----
    try:
        # Get all email recipients from the data
        data = load_data()
        recipients = data.get('email_recipients', [])
        
        if recipients:
            for email in recipients:
                try:
                    send_email_alert(title, message, email)
                    print(f"[ALERT] Email sent to {email}")
                except Exception as e:
                    print(f"[ALERT] Email notification to {email} failed: {e}")
                    logging.error(f"[ALERT] Email notification to {email} failed: {e}")
        else:
            print("[ALERT] No email recipients configured")
    except Exception as e:
        print(f"[ALERT] Email notification process failed: {e}")
        logging.error(f"[ALERT] Email notification process failed: {e}")

def monitor_stock(window_start=None, window_end=None, manual_refresh=False):
    data = load_data()
    today = get_today()
    current_price = fetch_sn_price()
    if current_price is None:
        print("Could not fetch SN price.")
        return
        
    # Determine which trading window we're using
    if 'active_window' in data and not (window_start and window_end):
        window_key = data['active_window']
        window_start, window_end = window_key.split('_to_')
    elif window_start and window_end:
        window_key = format_window_key(window_start, window_end)
    else:
        # Default to current month if no window is specified
        month = get_current_month()
        window_key = month

    # Calculate baseline based on window start date or default to first day of current month
    ticker = yf.Ticker(TICKER)
    
    # Convert window_start to datetime if it exists, otherwise use first day of current month
    if window_start:
        try:
            start_date = datetime.strptime(window_start, '%Y-%m-%d')
        except ValueError:
            print(f"Invalid start date format: {window_start}")
            start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Convert window_end to datetime if it exists, otherwise use first day of next month
    if window_end:
        try:
            end_date = datetime.strptime(window_end, '%Y-%m-%d')
            # Add one day to include the end date in the data
            end_date = end_date + timedelta(days=1)
        except ValueError:
            print(f"Invalid end date format: {window_end}")
            end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    
    # Get historical data for the window
    hist = ticker.history(start=start_date, end=end_date, interval='1d')
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

    if window_key not in data:
        # First run for this window: set only baseline and current price; leave peak unset
        data[window_key] = {
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
        print(f"Initialized baseline for window {window_key}: ${baseline_price:.2f} on {baseline_date}")
        return
    else:
        # Always update baseline to the correct value
        data[window_key]['baseline_date'] = baseline_date
        data[window_key]['baseline_price'] = baseline_price

    # Always update current price
    data[window_key]['current_price'] = current_price

    # If the peak was simulated, only clear it on manual refresh
    if manual_refresh and data[window_key].get('peak_simulated'):
        data[window_key]['peak_price'] = data[window_key].get('last_real_peak_price', data[window_key]['baseline_price'])
        data[window_key]['peak_date'] = data[window_key].get('last_real_peak_date', data[window_key]['baseline_date'])
        data[window_key]['peak_simulated'] = False
        save_data(data)
        print(f"Simulated peak cleared. Restored last real peak for window {window_key}: {data[window_key]['peak_price']} on {data[window_key]['peak_date']}")
    # If not manual refresh and peak was simulated, keep it as is

    # Check for new real peak (must be above both previous peak and baseline)
    last_real = data[window_key]['last_real_peak_price'] if data[window_key]['last_real_peak_price'] is not None else data[window_key]['baseline_price']
    if current_price > max(last_real, data[window_key]['baseline_price']):
        data[window_key]['peak_price'] = current_price
        data[window_key]['peak_date'] = today
        data[window_key]['last_real_peak_price'] = current_price
        data[window_key]['last_real_peak_date'] = today
        save_data(data)
        notify_peak(current_price)
        print(f"New peak for window {window_key}: ${current_price:.2f}")
    else:
        save_data(data)
        print(f"Checked: ${current_price:.2f} (Current peak: {data[window_key]['peak_price']})")

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
    .btn-group { display: flex; gap: 14px; justify-content: center; margin: 22px 0 14px 0; flex-wrap: wrap; }
    button { background: #1976d2; color: #fff; border: none; border-radius: 8px; padding: 12px 24px; font-size: 1.08em; font-weight: 500; cursor: pointer; transition: background 0.18s, box-shadow 0.18s; box-shadow: 0 1px 4px #1976d220; }
    button:hover, button:focus { background: #1565c0; outline: none; box-shadow: 0 2px 8px #1976d230; }
    #msg { text-align: center; margin-top: 12px; min-height: 28px; font-weight: 500; font-size: 1.08em; letter-spacing: 0.1px; }
    .spinner { display: inline-block; width: 22px; height: 22px; border: 3px solid #1976d2; border-radius: 50%; border-top: 3px solid #fff; animation: spin 1s linear infinite; margin-right: 8px; vertical-align: middle; }
    
    /* Trading window styles */
    .trading-window-inputs { display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 10px; border: 1px dashed #ccc; }
    .date-input-group { display: flex; align-items: center; justify-content: space-between; }
    .date-input-group label { font-weight: 500; color: #555; flex: 1; text-align: left; }
    .date-input-group input[type="date"] { flex: 2; padding: 8px; border: 1px solid #ddd; border-radius: 5px; font-family: inherit; }
    .window-btn { background: #4caf50; margin-top: 8px; }
    .window-btn:hover, .window-btn:focus { background: #388e3c; }
    
    /* Email management styles */
    .email-management { margin: 15px 0 25px; padding: 15px; background: #f0f8ff; border-radius: 10px; border: 1px dashed #1976d2; }
    .email-management h4 { margin: 0 0 15px; color: #1976d2; font-weight: 500; }
    .email-input-group { display: flex; gap: 10px; margin-bottom: 15px; }
    .email-input-group input { flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 5px; font-family: inherit; }
    .email-btn { background: #1976d2; padding: 8px 15px; margin: 0; }
    .email-list { max-height: 150px; overflow-y: auto; border-top: 1px solid #ddd; padding-top: 10px; }
    .email-item { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; }
    .email-address { font-size: 0.95em; color: #444; }
    .delete-email { background: #f44336; color: white; border: none; border-radius: 4px; padding: 3px 8px; cursor: pointer; font-size: 0.8em; }
    .delete-email:hover { background: #d32f2f; }
    .loading-placeholder { color: #888; font-style: italic; text-align: center; padding: 10px 0; }
    
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
      <h4>Trading Window: <span id="month"></span></h4>
      <div class="trading-window-inputs">
        <div class="date-input-group">
          <label for="window-start">Window Start Date:</label>
          <input type="date" id="window-start" name="window-start">
        </div>
        <div class="date-input-group">
          <label for="window-end">Window End Date:</label>
          <input type="date" id="window-end" name="window-end">
        </div>
        <button onclick="setTradingWindow()" class="window-btn">Set Trading Window</button>
      </div>
      
      <div class="email-management">
        <h4>Email Notifications</h4>
        <div class="email-input-group">
          <input type="email" id="new-email" placeholder="Enter email address...">
          <button onclick="addEmailRecipient()" class="email-btn">Add</button>
        </div>
        <div id="email-list" class="email-list">
          <!-- Email recipients will be listed here -->
          <div class="loading-placeholder">Loading recipients...</div>
        </div>
      </div>
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
    
    // Function to set the trading window
    function setTradingWindow() {
        const startDate = document.getElementById('window-start').value;
        const endDate = document.getElementById('window-end').value;
        
        if (!startDate || !endDate) {
            showMsg('Please select both start and end dates', 'red');
            return;
        }
        
        if (new Date(startDate) > new Date(endDate)) {
            showMsg('Start date must be before end date', 'red');
            return;
        }
        
        showSpinner('Setting trading window...');
        
        fetch('/api/set_trading_window', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                start_date: startDate,
                end_date: endDate
            })
        })
        .then(r => r.json())
        .then(data => {
            updateTable(data.status);
            showMsg(data.message || 'Trading window set!', 'green');
            
            // Update date inputs with the selected values for visual confirmation
            document.getElementById('window-start').value = data.status.window_start;
            document.getElementById('window-end').value = data.status.window_end;
            
            setTimeout(() => { document.getElementById('msg').innerText = ''; }, 3000);
        })
        .catch(() => {
            showMsg('Failed to set trading window', 'red');
        });
    }
    
    function updateTable(data) {
        // Update trading window heading and dates
        document.getElementById('month').innerText = data.month || '-';
        
        // If window dates are provided, update the date inputs
        if (data.window_start) {
            document.getElementById('window-start').value = data.window_start;
        }
        if (data.window_end) {
            document.getElementById('window-end').value = data.window_end;
        }
        
        // Update price and date fields
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
    
    // Store email recipients
    let emailRecipients = [];
    
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
    
    // Email management functions
    function loadEmailRecipients() {
        fetch('/api/email_recipients')
            .then(r => r.json())
            .then(data => {
                emailRecipients = data.recipients || [];
                renderEmailList();
            })
            .catch(() => {
                showMsg('Failed to load email recipients', 'red');
            });
    }
    
    function renderEmailList() {
        const listEl = document.getElementById('email-list');
        listEl.innerHTML = '';
        
        if (emailRecipients.length === 0) {
            listEl.innerHTML = '<div class="loading-placeholder">No recipients added yet</div>';
            return;
        }
        
        emailRecipients.forEach((email, index) => {
            const itemEl = document.createElement('div');
            itemEl.className = 'email-item';
            itemEl.innerHTML = `
                <span class="email-address">${email}</span>
                <button class="delete-email" onclick="removeEmailRecipient(${index})">Remove</button>
            `;
            listEl.appendChild(itemEl);
        });
    }
    
    function addEmailRecipient() {
        const emailInput = document.getElementById('new-email');
        const email = emailInput.value.trim();
        
        if (!email) {
            showMsg('Please enter an email address', 'red');
            return;
        }
        
        // Basic email validation
        if (!email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) {
            showMsg('Please enter a valid email address', 'red');
            return;
        }
        
        // Check if email already exists
        if (emailRecipients.includes(email)) {
            showMsg('This email is already in the list', 'red');
            return;
        }
        
        fetch('/api/add_email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                emailRecipients = data.recipients;
                renderEmailList();
                emailInput.value = '';
                showMsg('Email added successfully!', 'green');
                setTimeout(() => { document.getElementById('msg').innerText = ''; }, 1800);
            } else {
                showMsg(data.message || 'Failed to add email', 'red');
            }
        })
        .catch(() => {
            showMsg('Failed to add email', 'red');
        });
    }
    
    function removeEmailRecipient(index) {
        if (index < 0 || index >= emailRecipients.length) {
            return;
        }
        
        const emailToRemove = emailRecipients[index];
        
        fetch('/api/remove_email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: emailToRemove })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                emailRecipients = data.recipients;
                renderEmailList();
                showMsg('Email removed successfully', 'green');
                setTimeout(() => { document.getElementById('msg').innerText = ''; }, 1800);
            } else {
                showMsg(data.message || 'Failed to remove email', 'red');
            }
        })
        .catch(() => {
            showMsg('Failed to remove email', 'red');
        });
    }
    
    // Initialize everything
    loadStatus();
    loadEmailRecipients();
    startAutomaticChecking();
    </script>
    '''
    return render_template_string(html)

@app.route('/api/status')
def api_status():
    data = load_data()
    # Check if there's an active trading window set
    if 'active_window' in data:
        window_key = data['active_window']
        window_data = data.get(window_key, {})
        # Parse the window_key to get start and end dates
        start_date, end_date = window_key.split('_to_')
        return jsonify({
            "month": f"{start_date} to {end_date}",  # Display format
            "window_start": start_date,
            "window_end": end_date,
            **window_data
        })
    else:
        # Default to current month if no window is set
        month = get_current_month()
        month_data = data.get(month, {})
        return jsonify({"month": month, **month_data})

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    monitor_stock(manual_refresh=True)  # Force a check with manual refresh flag
    data = load_data()
    
    # Check if there's an active trading window set
    if 'active_window' in data:
        window_key = data['active_window']
        window_data = data.get(window_key, {})
        # Parse the window_key to get start and end dates
        start_date, end_date = window_key.split('_to_')
        return jsonify({
            "status": {
                "month": f"{start_date} to {end_date}",  # Display format
                "window_start": start_date,
                "window_end": end_date,
                **window_data
            }, 
            "message": "Refreshed!"
        })
    else:
        # Default to current month if no window is set
        month = get_current_month()
        month_data = data.get(month, {})
        return jsonify({"status": {"month": month, **month_data}, "message": "Refreshed!"})

@app.route('/api/set_trading_window', methods=['POST'])
def api_set_window():
    data = load_data()
    # Get start and end dates from the request
    start_date = request.json.get('start_date')
    end_date = request.json.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'error': 'Missing start_date or end_date'}), 400
    
    # Create a unique key for this window
    window_key = format_window_key(start_date, end_date)
    
    # Set this as the active window
    data['active_window'] = window_key
    
    # Initialize window data if it doesn't exist
    if window_key not in data:
        data[window_key] = {
            'baseline_price': None,
            'baseline_date': None,
            'peak_price': None,
            'peak_date': None,
            'current_price': None,
            'peak_simulated': False,
            'last_real_peak_price': None,
            'last_real_peak_date': None,
        }
    
    save_data(data)
    
    # Force a stock check to update the data with the new window
    monitor_stock()
    
    # Fetch the updated data
    updated_data = load_data()
    window_data = updated_data.get(window_key, {})
    
    return jsonify({
        'status': {
            'month': f"{start_date} to {end_date}",
            'window_start': start_date,
            'window_end': end_date,
            **window_data
        },
        'message': f'Trading window set from {start_date} to {end_date}!'
    })

@app.route('/api/clear', methods=['POST'])
def api_clear():
    data = load_data()
    # Check if there's an active window
    if 'active_window' in data:
        window_key = data['active_window']
        if window_key in data:
            del data[window_key]
        del data['active_window']
    else:
        # Default to current month
        month = get_current_month()
        if month in data:
            del data[month]
    
    save_data(data)
    return jsonify({'status': {}, 'message': 'Cleared!'})

@app.route('/api/email_recipients')
def api_email_recipients():
    data = load_data()
    recipients = data.get('email_recipients', [])
    return jsonify({'recipients': recipients})

@app.route('/api/add_email', methods=['POST'])
def api_add_email():
    email = request.json.get('email', '').strip()
    
    # Basic validation
    if not email or '@' not in email:
        return jsonify({'success': False, 'message': 'Invalid email address'})
    
    data = load_data()
    recipients = data.get('email_recipients', [])
    
    # Check if email already exists
    if email in recipients:
        return jsonify({'success': False, 'message': 'Email already exists'})
    
    # Add the new email
    recipients.append(email)
    data['email_recipients'] = recipients
    save_data(data)
    
    return jsonify({'success': True, 'recipients': recipients, 'message': 'Email added successfully'})

@app.route('/api/remove_email', methods=['POST'])
def api_remove_email():
    email = request.json.get('email', '').strip()
    
    if not email:
        return jsonify({'success': False, 'message': 'No email provided'})
    
    data = load_data()
    recipients = data.get('email_recipients', [])
    
    # Remove the email if it exists
    if email in recipients:
        recipients.remove(email)
        data['email_recipients'] = recipients
        save_data(data)
        return jsonify({'success': True, 'recipients': recipients, 'message': 'Email removed successfully'})
    else:
        return jsonify({'success': False, 'message': 'Email not found in the list'})

@app.route('/api/simulate_peak', methods=['POST'])
def api_simulate_peak():
    # Simulate a new peak by incrementing last real peak by 100 and triggering notify_peak
    data = load_data()
    
    # Check if there's an active trading window set
    if 'active_window' in data:
        window_key = data['active_window']
        if window_key not in data:
            return jsonify({"status": {"message": "No data for current trading window."}, "message": "No data found."})
    else:
        # Default to current month if no window is set
        window_key = get_current_month()
        if window_key not in data:
            return jsonify({"status": {"month": window_key}, "message": "No data for this month."})
    
    # Get the last real peak (or baseline if no real peak)
    last_real_peak = data[window_key]['last_real_peak_price'] if data[window_key]['last_real_peak_price'] is not None else data[window_key]['baseline_price']
    
    # Simulate a new peak by adding 100 to the last real peak
    simulated_peak = last_real_peak + 100
    data[window_key]['current_price'] = simulated_peak
    data[window_key]['peak_price'] = simulated_peak
    data[window_key]['peak_date'] = get_today()
    data[window_key]['peak_simulated'] = True
    save_data(data)
    
    # Send notification
    notify_peak(simulated_peak, is_simulation=True)
    
    # Build response based on window type
    if 'active_window' in data:
        # Parse window for display
        start_date, end_date = window_key.split('_to_')
        return jsonify({
            "status": {
                "month": f"{start_date} to {end_date}",
                "window_start": start_date,
                "window_end": end_date,
                **data[window_key]
            }, 
            "message": "Simulated peak!"
        })
    else:
        return jsonify({"status": {"month": window_key, **data[window_key]}, "message": "Simulated peak!"})

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
