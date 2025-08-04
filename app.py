from flask import Flask, jsonify, render_template
import json
import os
from datetime import datetime
import yfinance as yf
from sn_stock_monitor import notify_peak, get_current_month, get_today

app = Flask(__name__)
DATA_FILE = 'sn_monthly_data.json'
TICKER = 'NOW'


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def get_current_price():
    # Optionally, load the latest price from the data file, or fetch from yfinance if needed
    # For UI, we'll just show the last stored peak as current price for simplicity
    data = load_data()
    month = datetime.now().strftime('%Y-%m')
    if month in data:
        return data[month].get('current_price', data[month].get('peak_price', None))
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    data = load_data()
    month = datetime.now().strftime('%Y-%m')
    if month in data:
        month_data = data[month]
        return jsonify({
            'current_price': month_data.get('current_price', None),
            'baseline_price': month_data.get('baseline_price', None),
            'baseline_date': month_data.get('baseline_date', None),
            'peak_price': month_data.get('peak_price', None),
            'peak_date': month_data.get('peak_date', None)
        })
    else:
        return jsonify({'error': 'No data for this month'}), 404

@app.route('/api/refresh', methods=['POST'])
def refresh():
    TICKER = 'NOW'
    now = datetime.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = now
    # Fetch daily data for the month
    ticker = yf.Ticker(TICKER)
    hist = ticker.history(start=start_of_month, end=end, interval='1d')
    if hist.empty:
        return jsonify({'error': 'No data found from yfinance'}), 404
    # Baseline: first opening price
    baseline_row = hist.iloc[0]
    baseline_price = float(baseline_row['Open'])
    baseline_date = baseline_row.name.strftime('%Y-%m-%d')
    # Peak: highest price in the month
    peak_idx = hist['High'].idxmax()
    peak_price = float(hist.loc[peak_idx]['High'])
    peak_date = peak_idx.strftime('%Y-%m-%d')
    # If peak is not higher than baseline, set to N/A
    if peak_price > baseline_price:
        peak_price_out = peak_price
        peak_date_out = peak_date
    else:
        peak_price_out = None
        peak_date_out = None
    # Current price: fetch latest price
    current = ticker.history(period='1d', interval='1m')
    if not current.empty:
        current_price = float(current['Close'][-1])
    else:
        current_price = None
    return jsonify({
        'current_price': current_price,
        'baseline_price': baseline_price,
        'baseline_date': baseline_date,
        'peak_price': peak_price_out,
        'peak_date': peak_date_out
    })

@app.route('/api/simulate_peak', methods=['POST'])
def simulate_peak():
    TICKER = 'NOW'
    now = datetime.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = now
    ticker = yf.Ticker(TICKER)
    hist = ticker.history(start=start_of_month, end=end, interval='1d')
    if hist.empty:
        return jsonify({'error': 'No data found from yfinance'}), 404
    # Baseline: first opening price
    baseline_row = hist.iloc[0]
    baseline_price = float(baseline_row['Open'])
    baseline_date = baseline_row.name.strftime('%Y-%m-%d')
    # Real peak: highest price in the month
    peak_idx = hist['High'].idxmax()
    real_peak_price = float(hist.loc[peak_idx]['High'])
    real_peak_date = peak_idx.strftime('%Y-%m-%d')
    # Simulate a new peak
    simulated_peak = real_peak_price + 50
    simulated_peak_date = now.strftime('%Y-%m-%d')
    # Current price: set to simulated peak
    current_price = simulated_peak
    # Trigger notification
    notify_peak(simulated_peak, is_simulation=True)
    # Return simulated data
    return jsonify({
        'current_price': current_price,
        'baseline_price': baseline_price,
        'baseline_date': baseline_date,
        'peak_price': simulated_peak,
        'peak_date': simulated_peak_date
    })

@app.route('/api/clear_data', methods=['POST'])
def clear_data():
    with open(DATA_FILE, 'w') as f:
        json.dump({}, f)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)
